"""Ocena planu kalorycznego (D2b).

Trzy oddzielne wartosci:
- cel kcal planu (Profile.daily_kcal_target) - zmienia sie tylko jawnie: zapis profilu albo akceptacja sugestii,
- szacowane TDEE - wzor Mifflin-St Jeor dla aktualnej (usrednionej) masy; wylacznie informacyjnie,
- obserwowany trend masy - tempo zmiany z ostatnich tygodni i TDEE wynikajace z faktycznego spozycia.

Zasada: nie zmniejszamy kalorii tylko dlatego, ze spadla masa ciala. Korekta jest sugerowana dopiero, gdy trend
wyraznie odbiega od celu, trwa wystarczajaco dlugo i dane sa wystarczajace. Uzytkownik zawsze ja zatwierdza.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock, services
from .i18n import get_language, t
from .models import DayEntry, DayLog, Profile
from .schemas import PlanStatusOut

KCAL_PER_KG = 7700
TREND_WINDOW_DAYS = 28  # okno trendu masy (dni wstecz od dzis, nie wczesniej niz start planu)
TREND_MIN_MEASUREMENTS = 4
TREND_MIN_SPAN_DAYS = 14
TREND_AVERAGE_DAYS = 7  # "aktualna masa" = srednia pomiarow z 7 dni konczacych sie na ostatnim pomiarze
MIN_PLAN_DAYS_BEFORE_ADJUST = 21
REEVALUATION_DAYS = 28
REEVALUATION_WEIGHT_CHANGE_PCT = 3.0
INTAKE_MIN_COVERAGE = 0.7  # min. odsetek dni z wpisami jedzenia, by liczyc TDEE z obserwacji
TOLERANCE_MIN_PCT_PER_WEEK = 0.25  # minimalna tolerancja tempa: 0,25% masy / tydzien
TOLERANCE_RELATIVE = 0.5  # albo 50% oczekiwanego tempa, jesli wieksze
MAX_LOSS_PCT_PER_WEEK = 1.0
MAX_GAIN_PCT_PER_WEEK = 0.5
MIN_STEP_KCAL = 100
DEFAULT_STEP_KCAL = 150
MAX_STEP_KCAL = 200
MIN_TARGET_KCAL = {"male": 1500, "female": 1200}
# T2.7: prognoza osiagniecia wagi docelowej
TARGET_REACHED_KG = 0.3  # |waga docelowa - srednia masa| ponizej tej wartosci = osiagnieta
FORECAST_MIN_RATE_KG_PER_WEEK = 0.05  # wolniejsze tempo traktujemy jak brak zmiany
FORECAST_MAX_DAYS = 3 * 365


@dataclass
class _Measurement:
    log_date: date
    weight_kg: float


def _measurements(db: Session, user_id: int, date_from: date, date_to: date) -> list[_Measurement]:
    rows = db.execute(
        select(DayLog.log_date, DayEntry.weight_kg)
        .join(DayEntry, DayEntry.day_log_id == DayLog.id)
        .where(
            DayLog.user_id == user_id,
            DayEntry.entry_type == "weight",
            DayEntry.weight_kg.is_not(None),
            DayLog.log_date >= date_from,
            DayLog.log_date <= date_to,
        )
        .order_by(DayLog.log_date.asc())
    ).all()
    return [_Measurement(log_date, weight) for log_date, weight in rows]


def _slope_kg_per_day(points: list[_Measurement]) -> float:
    """Regresja liniowa masy wzgledem dnia (odporniejsza na wahania niz roznica pierwszy-ostatni)."""
    origin = points[0].log_date
    xs = [(point.log_date - origin).days for point in points]
    ys = [point.weight_kg for point in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True)) / denominator


def _intake(db: Session, user_id: int, date_from: date, date_to: date) -> tuple[float | None, float]:
    """Srednie spozycie z dni z jedzeniem oraz pokrycie okresu takimi dniami (0-1)."""
    day_logs = db.scalars(
        select(DayLog).where(DayLog.user_id == user_id, DayLog.log_date >= date_from, DayLog.log_date <= date_to)
    ).all()
    food_totals = [
        day_log.total_kcal
        for day_log in day_logs
        if any(entry.entry_type in services.CALORIC_ENTRY_TYPES for entry in day_log.entries)
    ]
    span_days = (date_to - date_from).days + 1
    if not food_totals:
        return None, 0.0
    return sum(food_totals) / len(food_totals), len(food_totals) / span_days


def _round10(value: float) -> float:
    return float(round(value / 10) * 10)


def evaluate_plan(db: Session, user_id: int) -> PlanStatusOut:
    profile: Profile | None = services.get_profile(db, user_id)
    if profile is None:
        raise services.NotFoundError(t("Nie znaleziono profilu."))
    status = _evaluate(db, user_id, profile)
    _add_forecast(status, profile, _recent_rate_kg_per_week(db, user_id))
    return status


def _recent_rate_kg_per_week(db: Session, user_id: int) -> float | None:
    """Tempo zmiany masy z ostatnich TREND_WINDOW_DAYS dni - niezaleznie od startu planu (prognoza, dane historyczne)."""
    latest = services.latest_weight_entry(db, user_id)
    if latest is None:
        return None
    last_date = latest.day_log.log_date
    points = _measurements(db, user_id, last_date - timedelta(days=TREND_WINDOW_DAYS - 1), last_date)
    if len(points) < TREND_MIN_MEASUREMENTS or (points[-1].log_date - points[0].log_date).days < TREND_MIN_SPAN_DAYS:
        return None
    return round(_slope_kg_per_day(points) * 7, 2)


def _add_forecast(status: PlanStatusOut, profile: Profile, recent_rate: float | None) -> None:
    """Prognoza daty osiagniecia wagi docelowej: z trendu ostatnich pomiarow (takze sprzed startu planu,
    np. z importu), a bez trendu - z tempa wynikajacego z planu.

    Tylko informacja - nie wplywa na cel kcal (D2b).
    """
    target = profile.target_weight_kg
    if target is None:
        return
    status.target_weight_kg = target
    current = status.trend_weight_kg if status.trend_weight_kg is not None else profile.weight_kg
    remaining = target - current
    status.target_weight_remaining_kg = round(remaining, 1)
    if abs(remaining) < TARGET_REACHED_KG:
        status.forecast_message = t("Waga docelowa {target} kg osiągnięta.", target=services.fmt_number(target))
        return
    if recent_rate is not None:
        rate, basis = recent_rate, "trend"
        source = t("przy obecnym trendzie ({rate})", rate=_fmt_rate(rate))
    else:
        rate, basis = status.expected_rate_kg_per_week, "plan"
        source = t("według tempa planu ({rate}; za mało pomiarów do trendu)", rate=_fmt_rate(rate)) if rate is not None else ""
    status.forecast_basis = basis if rate is not None else None
    if rate is None or abs(rate) < FORECAST_MIN_RATE_KG_PER_WEEK or rate * remaining <= 0:
        if basis == "trend":
            status.forecast_message = t(
                "Obecny trend ({rate}) nie prowadzi do wagi docelowej {target} kg.", rate=_fmt_rate(rate), target=services.fmt_number(target)
            )
        else:
            status.forecast_message = t("Plan nie zakłada zmiany masy w kierunku wagi docelowej {target} kg.", target=services.fmt_number(target))
        return
    days = round(remaining / rate * 7)
    if days > FORECAST_MAX_DAYS:
        status.forecast_message = t("Waga docelowa {target} kg za ponad 3 lata – {source}.", target=services.fmt_number(target), source=source)
        return
    status.forecast_date = clock.today() + timedelta(days=days)
    status.forecast_message = t(
        "Waga docelowa {target} kg około {date} (za ok. {weeks} tyg.) – {source}.",
        target=services.fmt_number(target),
        date=services.fmt_date(status.forecast_date),
        weeks=max(1, round(days / 7)),
        source=source,
    )


def _evaluate(db: Session, user_id: int, profile: Profile) -> PlanStatusOut:

    today = clock.today()
    plan_started_on = profile.plan_started_on or today
    plan_days = (today - plan_started_on).days
    target = profile.daily_kcal_target
    plan_tdee = profile.plan_tdee_kcal or services.calculate_tdee(profile)
    notes: list[str] = []

    status = PlanStatusOut(
        goal_type=profile.goal_type,
        plan_started_on=plan_started_on,
        plan_days=plan_days,
        plan_weight_kg=profile.weight_kg,
        plan_tdee_kcal=plan_tdee,
        daily_kcal_target=target,
        status="no_data",
        recommendation="keep",
        message="",
    )

    # Aktualna masa: ostatni pomiar i srednia z 7 dni (niezaleznie od startu planu).
    latest = services.latest_weight_entry(db, user_id)
    if latest is None:
        status.message = t("Brak pomiarów wagi. Dodawaj wpis „Waga” regularnie (np. 2–3 razy w tygodniu, rano, na czczo).")
        return status
    latest_date = latest.day_log.log_date
    recent = _measurements(db, user_id, latest_date - timedelta(days=TREND_AVERAGE_DAYS - 1), latest_date)
    trend_weight = sum(point.weight_kg for point in recent) / len(recent)
    status.current_weight_kg = latest.weight_kg
    status.current_weight_date = latest_date
    status.trend_weight_kg = round(trend_weight, 2)
    status.weight_change_since_plan_kg = round(trend_weight - profile.weight_kg, 2)
    status.weight_change_since_plan_pct = round((trend_weight - profile.weight_kg) / profile.weight_kg * 100, 1)
    status.estimated_tdee_kcal = services.calculate_tdee(profile, weight_kg=trend_weight)
    status.reevaluation_due = plan_days >= REEVALUATION_DAYS or abs(status.weight_change_since_plan_pct) >= REEVALUATION_WEIGHT_CHANGE_PCT

    # Oczekiwane tempo wynika z planu: (cel - TDEE planu) -> kg/tydzien, z tolerancja i limitami bezpieczenstwa.
    expected = (target - plan_tdee) * 7 / KCAL_PER_KG
    tolerance = max(abs(expected) * TOLERANCE_RELATIVE, trend_weight * TOLERANCE_MIN_PCT_PER_WEEK / 100)
    low, high = expected - tolerance, expected + tolerance
    low = max(low, -trend_weight * MAX_LOSS_PCT_PER_WEEK / 100)
    high = min(high, trend_weight * MAX_GAIN_PCT_PER_WEEK / 100)
    status.expected_rate_kg_per_week = round(expected, 2)
    status.expected_rate_low_kg_per_week = round(low, 2)
    status.expected_rate_high_kg_per_week = round(high, 2)

    # Trend: tylko pomiary od startu planu (starsze odzwierciedlaja poprzedni plan).
    window_start = max(today - timedelta(days=TREND_WINDOW_DAYS - 1), plan_started_on)
    points = _measurements(db, user_id, window_start, today)
    status.measurements_count = len(points)
    span = (points[-1].log_date - points[0].log_date).days if points else 0
    if len(points) < TREND_MIN_MEASUREMENTS or span < TREND_MIN_SPAN_DAYS:
        status.status = "no_data" if plan_days >= TREND_MIN_SPAN_DAYS else "wait"
        status.message = t(
            "Za mało danych do oceny trendu: potrzeba co najmniej {needed} pomiarów z {span_needed} dni od startu planu "
            "(jest {count} z {span} dni). Cel pozostaje bez zmian.",
            needed=TREND_MIN_MEASUREMENTS,
            span_needed=TREND_MIN_SPAN_DAYS,
            count=len(points),
            span=span,
        )
        _add_tdee_note(status, notes)
        status.notes = notes
        return status

    slope_week = _slope_kg_per_day(points) * 7
    status.observed_rate_kg_per_week = round(slope_week, 2)
    status.observed_rate_pct_per_week = round(slope_week / trend_weight * 100, 2)

    intake_avg, coverage = _intake(db, user_id, points[0].log_date, points[-1].log_date)
    status.intake_avg_kcal = round(intake_avg, 0) if intake_avg is not None else None
    status.intake_coverage_pct = round(coverage * 100, 0)
    if intake_avg is not None and coverage >= INTAKE_MIN_COVERAGE:
        status.observed_tdee_kcal = round(intake_avg - slope_week / 7 * KCAL_PER_KG, 0)
    else:
        notes.append(
            t(
                "Wpisy jedzenia pokrywają {coverage}% dni okresu – za mało (min. {minimum}), by oszacować rzeczywiste zapotrzebowanie z obserwacji.",
                coverage=f"{status.intake_coverage_pct:.0f}",
                minimum=f"{INTAKE_MIN_COVERAGE:.0%}",
            )
        )

    _add_tdee_note(status, notes)

    if low <= slope_week <= high:
        status.status = "on_track"
        status.message = t(
            "Plan działa: tempo {rate} mieści się w zakresie {low} … {high} Cel pozostaje: {target} kcal.",
            rate=_fmt_rate(slope_week),
            low=_fmt_rate(low),
            high=_fmt_rate(high),
            target=f"{target:.0f}",
        )
        status.notes = notes
        return status

    status.status = "below_range" if slope_week < low else "above_range"
    direction = "increase" if slope_week < low else "decrease"
    status.message = _off_track_message(profile.goal_type, slope_week, low, high)

    if plan_days < MIN_PLAN_DAYS_BEFORE_ADJUST:
        status.status = "wait"
        status.message += " " + t(
            "Plan trwa dopiero {days} dni – poczekaj do {minimum} dni przed korektą.", days=plan_days, minimum=MIN_PLAN_DAYS_BEFORE_ADJUST
        )
        status.notes = notes
        return status

    suggested = _suggest_target(profile, target, direction, status.observed_tdee_kcal, expected, low, high)
    floor = MIN_TARGET_KCAL.get(profile.sex, 1500)
    if suggested is None:
        status.message += " " + t(
            "Obecny cel ({target} kcal) jest już na dolnej granicy ({floor} kcal) – dalsze obniżanie wymaga konsultacji ze specjalistą.",
            target=f"{target:.0f}",
            floor=floor,
        )
    else:
        status.recommendation = direction
        status.suggested_target_kcal = suggested
        template = (
            "Sugerowane zwiększenie celu do {suggested} kcal ({delta} kcal)."
            if direction == "increase"
            else "Sugerowane zmniejszenie celu do {suggested} kcal ({delta} kcal)."
        )
        status.message += " " + t(template, suggested=f"{suggested:.0f}", delta=f"{suggested - target:+.0f}")
    status.notes = notes
    return status


def _suggest_target(profile: Profile, target: float, direction: str, observed_tdee: float | None, expected: float, low: float, high: float) -> float | None:
    sign = 1 if direction == "increase" else -1
    if observed_tdee is not None:
        desired_rate = min(max(expected, low), high)
        ideal = observed_tdee + desired_rate * KCAL_PER_KG / 7
        delta = ideal - target
        if delta * sign <= 0:  # obserwacja wskazuje przeciwny kierunek - minimalny krok
            delta = sign * MIN_STEP_KCAL
    else:
        delta = sign * DEFAULT_STEP_KCAL
    delta = sign * min(max(abs(delta), MIN_STEP_KCAL), MAX_STEP_KCAL)
    suggested = _round10(target + delta)
    floor = MIN_TARGET_KCAL.get(profile.sex, 1500)
    if sign < 0 and suggested < floor:
        if target <= floor:
            return None
        suggested = float(floor)
    return suggested


def _add_tdee_note(status: PlanStatusOut, notes: list[str]) -> None:
    if status.estimated_tdee_kcal is None or status.plan_tdee_kcal is None:
        return
    diff = status.estimated_tdee_kcal - status.plan_tdee_kcal
    if abs(diff) >= 20:
        template = (
            "Szacowane zapotrzebowanie (wzór, średnia masa {weight} kg) spadło do {tdee} kcal (start planu: {plan_tdee} kcal). "
            "To samo w sobie nie zmienia celu – decyduje faktyczny trend masy."
            if diff < 0
            else "Szacowane zapotrzebowanie (wzór, średnia masa {weight} kg) wzrosło do {tdee} kcal (start planu: {plan_tdee} kcal). "
            "To samo w sobie nie zmienia celu – decyduje faktyczny trend masy."
        )
        notes.append(
            t(
                template,
                weight=services.fmt_number(status.trend_weight_kg),
                tdee=f"{status.estimated_tdee_kcal:.0f}",
                plan_tdee=f"{status.plan_tdee_kcal:.0f}",
            )
        )


def _fmt_rate(kg_per_week: float) -> str:
    value = f"{kg_per_week:+.2f}"
    return t("{value} kg/tydz.", value=value.replace(".", ",") if get_language() == "pl" else value)


def _off_track_message(goal_type: str, rate: float, low: float, high: float) -> str:
    band = t("(oczekiwane {low} … {high})", low=_fmt_rate(low), high=_fmt_rate(high))
    if goal_type == "cut":
        template = "Masa spada za szybko: {rate} {band}." if rate < low else "Redukcja zwolniła: {rate} {band}."
    elif goal_type == "bulk":
        template = "Przyrost masy jest za wolny: {rate} {band}." if rate < low else "Masa rośnie za szybko: {rate} {band}."
    else:
        template = "Masa spada: {rate} {band}." if rate < low else "Masa rośnie: {rate} {band}."
    return t(template, rate=_fmt_rate(rate), band=band)


def apply_suggestion(db: Session, user_id: int, expected_target_kcal: float) -> PlanStatusOut:
    """Akceptacja sugestii: nowy cel, nowy start planu, waga planu = aktualna srednia masa."""
    status = evaluate_plan(db, user_id)
    if status.suggested_target_kcal is None:
        raise services.ConflictError(t("Brak aktualnej sugestii zmiany celu."))
    if abs(status.suggested_target_kcal - expected_target_kcal) >= 1:
        raise services.ConflictError(t("Sugestia zmieniła się w międzyczasie. Odśwież ocenę planu."))
    profile = services.get_profile(db, user_id)
    profile.weight_kg = round(status.trend_weight_kg, 1)
    plan_tdee = status.observed_tdee_kcal or status.estimated_tdee_kcal or services.calculate_tdee(profile)
    services.set_plan_target(db, profile, status.suggested_target_kcal, plan_tdee)
    return evaluate_plan(db, user_id)
