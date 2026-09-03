import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime

from slugify import slugify
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from .diagnostics import delete_user_diagnostics
from .models import DayEntry, DayLog, Profile, User
from .schemas import DaySummaryOut, ProfileIn, ReportDayOut, ReportSummaryOut
from .security import hash_pin, validate_pin, verify_pin

POLISH_TRANSLATION_TABLE = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ż": "z",
        "ź": "z",
    }
)

ACTIVITY_MULTIPLIER = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "athlete": 1.9,
}

ENTRY_TYPE_LABELS = {
    "weight": "Waga",
    "waist": "Obwod pasa",
    "breakfast": "Sniadanie",
    "lunch": "Obiad",
    "dinner": "Kolacja",
    "snack": "Przekaska",
    "daily_balance": "Bilans dnia",
}

MEAL_ENTRY_TYPES = {"breakfast", "lunch", "dinner", "snack"}
SINGLE_ENTRY_TYPES = {"weight", "waist", "daily_balance"}
ORDINAL_SUFFIXES = {
    2: "Drugie",
    3: "Trzecie",
    4: "Czwarte",
    5: "Piate",
    6: "Szoste",
    7: "Siodme",
    8: "Osme",
    9: "Dziewiate",
    10: "Dziesiate",
}

COMMAND_SHOW_TODAY = {"pokaz dzis", "pokaz dzien", "stan dnia"}
COMMAND_SUMMARY = {"podsumuj dzien", "podsumowanie dnia", "pokaz podsumowanie"}
COMMAND_UNDO = {"cofnij ostatni", "cofnij wpis", "undo"}
DELETE_POSITION_PATTERN = re.compile(r"\busun(?:\s+pozycje)?(?:\s+nr)?\s+(\d+)\b", flags=re.IGNORECASE)


@dataclass
class ParsedEntryInput:
    entry_type: str
    log_date: date | None
    source_text: str
    kcal: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    protein_g: float | None = None
    weight_kg: float | None = None
    waist_cm: float | None = None


def _normalize_text(raw: str) -> str:
    token = raw.strip().lower().translate(POLISH_TRANSLATION_TABLE)
    token = unicodedata.normalize("NFKD", token)
    token = "".join(char for char in token if not unicodedata.combining(char))
    token = " ".join(token.replace("-", " ").split())
    return token


def _parse_decimal(raw: str) -> float:
    normalized = raw.strip().replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if not match:
        raise ValueError("Nie znaleziono poprawnej liczby.")
    return float(match.group(0))


def parse_date_value(raw: str) -> date:
    value = raw.strip()
    formats = ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y")
    for pattern in formats:
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise ValueError("Niepoprawny format daty. Uzyj YYYY-MM-DD, DD.MM.YYYY, DD-MM-YYYY albo DD/MM/YYYY.")


def _extract_optional_date(lines: list[str]) -> tuple[date | None, list[str]]:
    if not lines:
        return None, []
    first = lines[0]
    if _normalize_text(first).startswith("data:"):
        _, _, value = first.partition(":")
        return parse_date_value(value), lines[1:]
    return None, lines


def _parse_measurement_line(line: str, field_name: str) -> float:
    _, _, value = line.partition(":")
    if not value.strip():
        raise ValueError(f"Brak wartosci dla pola '{field_name}'.")
    return _parse_decimal(value)


def _meal_template_help(entry_type: str) -> str:
    title = ENTRY_TYPE_LABELS[entry_type]
    return (
        f"{title}\n"
        "Ilosc kalorii: 540\n"
        "Weglowodany: 48\n"
        "Tluszcze: 18\n"
        "Bialko: 32"
    )


def _field_alias(key: str) -> str | None:
    normalized = _normalize_text(key).rstrip(":")
    aliases = {
        "ilosc kalorii": "kcal",
        "kalorie": "kcal",
        "kcal": "kcal",
        "weglowodany": "carbs_g",
        "tluszcze": "fat_g",
        "bialko": "protein_g",
    }
    return aliases.get(normalized)


def parse_template_message(message: str) -> ParsedEntryInput:
    raw_lines = [line.strip() for line in message.splitlines()]
    lines = [line for line in raw_lines if line]
    log_date, lines = _extract_optional_date(lines)
    if not lines:
        raise ValueError("Brak tresci wpisu po linii Data:. Uzyj jednego z gotowych szablonow.")

    header = lines[0].rstrip(":")
    normalized_header = _normalize_text(header)

    if normalized_header.startswith("waga:"):
        return ParsedEntryInput(
            entry_type="weight",
            log_date=log_date,
            source_text=message.strip(),
            weight_kg=_parse_measurement_line(lines[0], "Waga"),
        )

    if normalized_header.startswith("obwod pasa:"):
        return ParsedEntryInput(
            entry_type="waist",
            log_date=log_date,
            source_text=message.strip(),
            waist_cm=_parse_measurement_line(lines[0], "Obwod pasa"),
        )

    header_map = {
        "waga": "weight",
        "obwod pasa": "waist",
        "sniadanie": "breakfast",
        "obiad": "lunch",
        "kolacja": "dinner",
        "przekaska": "snack",
        "bilans dnia": "daily_balance",
    }
    entry_type = header_map.get(normalized_header)
    if not entry_type:
        raise ValueError(
            "Nie rozpoznano typu wpisu. Uzyj jednego z naglowkow: Waga, Obwod pasa, Sniadanie, Obiad, Kolacja, Przekaska, Bilans dnia."
        )

    if entry_type == "weight":
        if len(lines) < 2:
            raise ValueError("Dla wpisu 'Waga' podaj druga linie w formacie 'Waga: 82.4 kg'.")
        return ParsedEntryInput(
            entry_type="weight",
            log_date=log_date,
            source_text=message.strip(),
            weight_kg=_parse_measurement_line(lines[1], "Waga"),
        )

    if entry_type == "waist":
        if len(lines) < 2:
            raise ValueError("Dla wpisu 'Obwod pasa' podaj druga linie w formacie 'Obwod pasa: 91 cm'.")
        return ParsedEntryInput(
            entry_type="waist",
            log_date=log_date,
            source_text=message.strip(),
            waist_cm=_parse_measurement_line(lines[1], "Obwod pasa"),
        )

    values: dict[str, float] = {}
    for line in lines[1:]:
        if ":" not in line:
            raise ValueError(f"Niepoprawna linia: '{line}'. Kazda wartosc musi miec format 'Pole: liczba'.")
        key, _, raw_value = line.partition(":")
        alias = _field_alias(key)
        if not alias:
            raise ValueError(f"Nieznane pole '{key}'. Dla wpisow dziennych uzyj: Ilosc kalorii, Weglowodany, Tluszcze, Bialko.")
        if not raw_value.strip():
            raise ValueError(f"Brak wartosci dla pola '{key}'.")
        values[alias] = _parse_decimal(raw_value)

    required_fields = {"kcal", "carbs_g", "fat_g", "protein_g"}
    missing = [field for field in required_fields if field not in values]
    if missing:
        raise ValueError(
            "Brakuje pol w szablonie. Wymagane pola: Ilosc kalorii, Weglowodany, Tluszcze, Bialko.\n\n"
            + _meal_template_help(entry_type)
        )

    return ParsedEntryInput(
        entry_type=entry_type,
        log_date=log_date,
        source_text=message.strip(),
        kcal=values["kcal"],
        carbs_g=values["carbs_g"],
        fat_g=values["fat_g"],
        protein_g=values["protein_g"],
    )


def calculate_target(profile: ProfileIn) -> float:
    sex_factor = 5 if profile.sex == "male" else -161
    bmr = 10 * profile.weight_kg + 6.25 * profile.height_cm - 5 * profile.age + sex_factor
    tdee = bmr * ACTIVITY_MULTIPLIER[profile.activity_level]
    if profile.goal_type == "cut":
        tdee = tdee * (1 - profile.goal_delta_pct)
    elif profile.goal_type == "bulk":
        tdee = tdee * (1 + profile.goal_delta_pct)
    return round(tdee, 0)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.display_name)))


def create_user(db: Session, display_name: str, pin: str) -> User:
    if not validate_pin(pin):
        raise ValueError("PIN must have 4-8 digits")
    slug_base = slugify(display_name)[:50] or "user"
    slug = slug_base
    suffix = 1
    while db.scalar(select(User).where(User.slug == slug)):
        suffix += 1
        slug = f"{slug_base}-{suffix}"
    user = User(slug=slug, display_name=display_name, pin_hash=hash_pin(pin), is_active=True)
    db.add(user)
    db.flush()
    profile = Profile(user_id=user.id)
    db.add(profile)
    db.flush()
    return user


def require_user_pin(db: Session, user_id: int, pin: str) -> User | None:
    if not validate_pin(pin):
        return None
    user = db.get(User, user_id)
    if not user or not verify_pin(pin, user.pin_hash):
        return None
    return user


def get_day_log(db: Session, user_id: int, log_date: date) -> DayLog | None:
    return db.scalar(select(DayLog).where(DayLog.user_id == user_id, DayLog.log_date == log_date))


def get_or_create_day_log(db: Session, user_id: int, log_date: date) -> DayLog:
    day_log = get_day_log(db, user_id=user_id, log_date=log_date)
    if day_log:
        return day_log

    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    target = profile.daily_kcal_target if profile else 0.0
    day_log = DayLog(
        user_id=user_id,
        log_date=log_date,
        status="open",
        daily_kcal_target_snapshot=target,
        total_kcal=0.0,
        total_carbs_g=0.0,
        total_fat_g=0.0,
        total_protein_g=0.0,
        balance_mode=False,
    )
    db.add(day_log)
    db.flush()
    return day_log


def upsert_profile(db: Session, user_id: int, payload: ProfileIn) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
    profile.sex = payload.sex
    profile.age = payload.age
    profile.height_cm = payload.height_cm
    profile.weight_kg = payload.weight_kg
    profile.activity_level = payload.activity_level
    profile.goal_type = payload.goal_type
    profile.goal_delta_pct = payload.goal_delta_pct
    profile.daily_kcal_target = calculate_target(payload)
    profile.updated_at = datetime.utcnow()
    today_day_log = get_day_log(db, user_id=user_id, log_date=date.today())
    if today_day_log and today_day_log.status == "open":
        today_day_log.daily_kcal_target_snapshot = profile.daily_kcal_target
    db.flush()
    return profile


def delete_user(db: Session, user: User) -> None:
    delete_user_diagnostics(user)
    db.delete(user)
    db.flush()


def day_summary(day_log: DayLog) -> DaySummaryOut:
    return DaySummaryOut(
        user_id=day_log.user_id,
        log_date=day_log.log_date,
        status=day_log.status,
        total_kcal=round(day_log.total_kcal, 1),
        target_kcal=round(day_log.daily_kcal_target_snapshot, 1),
        total_carbs_g=round(day_log.total_carbs_g, 1),
        total_fat_g=round(day_log.total_fat_g, 1),
        total_protein_g=round(day_log.total_protein_g, 1),
        balance_mode=bool(day_log.balance_mode),
    )


def list_day_logs(db: Session, user_id: int, limit: int = 30) -> list[DayLog]:
    safe_limit = min(max(limit, 1), 180)
    days = list(
        db.scalars(
            select(DayLog)
            .where(DayLog.user_id == user_id)
            .order_by(DayLog.log_date.desc())
            .limit(safe_limit)
        )
    )
    for day in days:
        recalculate_day_totals(db, day)
    return days


def list_day_entries(db: Session, day_log: DayLog) -> list[DayEntry]:
    return list(
        db.scalars(
            select(DayEntry)
            .where(DayEntry.day_log_id == day_log.id)
            .order_by(DayEntry.entry_order.asc(), DayEntry.id.asc())
        )
    )


def day_entry_by_id(db: Session, day_log: DayLog, entry_id: int) -> DayEntry | None:
    return db.scalar(select(DayEntry).where(DayEntry.day_log_id == day_log.id, DayEntry.id == entry_id))


def day_entry_by_position(db: Session, day_log: DayLog, position: int) -> DayEntry | None:
    if position < 1:
        return None
    entries = list_day_entries(db, day_log)
    if position > len(entries):
        return None
    return entries[position - 1]


def _entry_meal_label(entry_type: str, count: int) -> str:
    base = ENTRY_TYPE_LABELS[entry_type]
    if count <= 1:
        return base
    suffix = ORDINAL_SUFFIXES.get(count, f"Nr {count}")
    return f"{base} {suffix}"


def refresh_day_entries(db: Session, day_log: DayLog) -> list[DayEntry]:
    entries = list_day_entries(db, day_log)
    meal_counters = {entry_type: 0 for entry_type in MEAL_ENTRY_TYPES}
    for index, entry in enumerate(entries, start=1):
        entry.entry_order = index
        if entry.entry_type in MEAL_ENTRY_TYPES:
            meal_counters[entry.entry_type] += 1
            entry.entry_label = _entry_meal_label(entry.entry_type, meal_counters[entry.entry_type])
        else:
            entry.entry_label = ENTRY_TYPE_LABELS[entry.entry_type]
    db.flush()
    return entries


def recalculate_day_totals(db: Session, day_log: DayLog) -> DayLog:
    entries = list_day_entries(db, day_log)
    balance_entry = next((entry for entry in entries if entry.entry_type == "daily_balance"), None)
    if balance_entry:
        day_log.total_kcal = round(balance_entry.kcal or 0.0, 1)
        day_log.total_carbs_g = round(balance_entry.carbs_g or 0.0, 1)
        day_log.total_fat_g = round(balance_entry.fat_g or 0.0, 1)
        day_log.total_protein_g = round(balance_entry.protein_g or 0.0, 1)
        day_log.balance_mode = True
    else:
        total_kcal = 0.0
        total_carbs = 0.0
        total_fat = 0.0
        total_protein = 0.0
        for entry in entries:
            if entry.entry_type not in MEAL_ENTRY_TYPES:
                continue
            total_kcal += entry.kcal or 0.0
            total_carbs += entry.carbs_g or 0.0
            total_fat += entry.fat_g or 0.0
            total_protein += entry.protein_g or 0.0
        day_log.total_kcal = round(total_kcal, 1)
        day_log.total_carbs_g = round(total_carbs, 1)
        day_log.total_fat_g = round(total_fat, 1)
        day_log.total_protein_g = round(total_protein, 1)
        day_log.balance_mode = False
    db.flush()
    return day_log


def _next_entry_order(db: Session, day_log: DayLog) -> int:
    return 1 + (
        db.scalar(select(DayEntry.entry_order).where(DayEntry.day_log_id == day_log.id).order_by(desc(DayEntry.entry_order)).limit(1))
        or 0
    )


def _single_entry_for_type(db: Session, day_log: DayLog, entry_type: str, exclude_entry_id: int | None = None) -> DayEntry | None:
    query = select(DayEntry).where(DayEntry.day_log_id == day_log.id, DayEntry.entry_type == entry_type)
    if exclude_entry_id is not None:
        query = query.where(DayEntry.id != exclude_entry_id)
    return db.scalar(query.order_by(DayEntry.entry_order.asc(), DayEntry.id.asc()))


def _apply_entry_payload_to_model(entry: DayEntry, payload: ParsedEntryInput) -> None:
    entry.entry_type = payload.entry_type
    entry.source_text = payload.source_text
    entry.kcal = payload.kcal
    entry.carbs_g = payload.carbs_g
    entry.fat_g = payload.fat_g
    entry.protein_g = payload.protein_g
    entry.weight_kg = payload.weight_kg
    entry.waist_cm = payload.waist_cm


def create_day_entry(db: Session, day_log: DayLog, payload: ParsedEntryInput) -> DayEntry:
    if payload.entry_type in SINGLE_ENTRY_TYPES:
        existing = _single_entry_for_type(db, day_log, payload.entry_type)
        if existing:
            _apply_entry_payload_to_model(existing, payload)
            refresh_day_entries(db, day_log)
            recalculate_day_totals(db, day_log)
            return existing

    entry = DayEntry(
        day_log_id=day_log.id,
        entry_order=_next_entry_order(db, day_log),
        entry_type=payload.entry_type,
        entry_label=ENTRY_TYPE_LABELS[payload.entry_type],
        source_text=payload.source_text,
        kcal=payload.kcal,
        carbs_g=payload.carbs_g,
        fat_g=payload.fat_g,
        protein_g=payload.protein_g,
        weight_kg=payload.weight_kg,
        waist_cm=payload.waist_cm,
    )
    db.add(entry)
    db.flush()
    refresh_day_entries(db, day_log)
    recalculate_day_totals(db, day_log)
    return entry


def update_day_entry_from_payload(
    db: Session,
    *,
    entry: DayEntry,
    user_id: int,
    payload: ParsedEntryInput,
    fallback_date: date,
) -> tuple[DayEntry, DayLog, DayLog | None]:
    source_day = entry.day_log
    target_date = payload.log_date or fallback_date
    target_day = get_or_create_day_log(db, user_id=user_id, log_date=target_date)
    changed_day = source_day.id != target_day.id

    if changed_day:
        entry.day_log_id = target_day.id
        entry.entry_order = _next_entry_order(db, target_day)

    _apply_entry_payload_to_model(entry, payload)

    if payload.entry_type in SINGLE_ENTRY_TYPES:
        duplicate = _single_entry_for_type(db, target_day, payload.entry_type, exclude_entry_id=entry.id)
        if duplicate:
            db.delete(duplicate)
            db.flush()

    refresh_day_entries(db, target_day)
    recalculate_day_totals(db, target_day)

    old_day = None
    if changed_day:
        refresh_day_entries(db, source_day)
        recalculate_day_totals(db, source_day)
        old_day = source_day

    return entry, target_day, old_day


def delete_day_entry_by_id(db: Session, day_log: DayLog, entry_id: int) -> DayEntry | None:
    entry = day_entry_by_id(db, day_log, entry_id)
    if not entry:
        return None
    db.delete(entry)
    db.flush()
    refresh_day_entries(db, day_log)
    recalculate_day_totals(db, day_log)
    return entry


def delete_day_entry_by_position(db: Session, day_log: DayLog, position: int) -> DayEntry | None:
    entry = day_entry_by_position(db, day_log, position)
    if not entry:
        return None
    db.delete(entry)
    db.flush()
    refresh_day_entries(db, day_log)
    recalculate_day_totals(db, day_log)
    return entry


def clear_day_entries(db: Session, day_log: DayLog) -> int:
    entries = list_day_entries(db, day_log)
    count = len(entries)
    for entry in entries:
        db.delete(entry)
    db.flush()
    day_log.total_kcal = 0.0
    day_log.total_carbs_g = 0.0
    day_log.total_fat_g = 0.0
    day_log.total_protein_g = 0.0
    day_log.balance_mode = False
    db.flush()
    return count


def undo_last_entry(db: Session, day_log: DayLog) -> DayEntry | None:
    entry = db.scalar(select(DayEntry).where(DayEntry.day_log_id == day_log.id).order_by(desc(DayEntry.entry_order)).limit(1))
    if not entry:
        return None
    db.delete(entry)
    db.flush()
    refresh_day_entries(db, day_log)
    recalculate_day_totals(db, day_log)
    return entry


def close_day(db: Session, day_log: DayLog) -> DayLog:
    day_log.status = "closed"
    day_log.closed_at = datetime.utcnow()
    db.flush()
    return day_log


def reopen_day(db: Session, day_log: DayLog) -> DayLog:
    day_log.status = "open"
    day_log.closed_at = None
    db.flush()
    return day_log


def report_for_range(db: Session, user_id: int, date_from: date, date_to: date) -> ReportSummaryOut:
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    days = list(
        db.scalars(
            select(DayLog)
            .where(DayLog.user_id == user_id, DayLog.log_date >= date_from, DayLog.log_date <= date_to)
            .order_by(DayLog.log_date.asc())
        )
    )
    points: list[ReportDayOut] = []
    entries_count = 0
    total_kcal = 0.0
    total_target = 0.0
    above_target = 0
    below_target = 0
    equal_target = 0

    for day in days:
        recalculate_day_totals(db, day)
        entries = db.scalar(select(func.count(DayEntry.id)).where(DayEntry.day_log_id == day.id)) or 0
        entries_count += int(entries)
        total_kcal += day.total_kcal
        total_target += day.daily_kcal_target_snapshot
        if day.total_kcal > day.daily_kcal_target_snapshot:
            above_target += 1
        elif day.total_kcal < day.daily_kcal_target_snapshot:
            below_target += 1
        else:
            equal_target += 1
        points.append(
            ReportDayOut(
                log_date=day.log_date,
                total_kcal=round(day.total_kcal, 1),
                target_kcal=round(day.daily_kcal_target_snapshot, 1),
                total_carbs_g=round(day.total_carbs_g, 1),
                total_fat_g=round(day.total_fat_g, 1),
                total_protein_g=round(day.total_protein_g, 1),
                balance_mode=bool(day.balance_mode),
                status=day.status,
                entries=int(entries),
            )
        )

    days_count = len(days)
    average_kcal = round(total_kcal / days_count, 1) if days_count else 0.0
    average_target = round(total_target / days_count, 1) if days_count else 0.0
    return ReportSummaryOut(
        date_from=date_from,
        date_to=date_to,
        days_count=days_count,
        entries_count=entries_count,
        total_kcal=round(total_kcal, 1),
        average_kcal=average_kcal,
        average_target_kcal=average_target,
        above_target_days=above_target,
        below_target_days=below_target,
        equal_target_days=equal_target,
        points=points,
    )


def parse_month_to_range(month_value: str) -> tuple[date, date]:
    year_text, month_text = month_value.split("-", maxsplit=1)
    year = int(year_text)
    month = int(month_text)
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def format_entry_summary(entry: DayEntry) -> str:
    if entry.entry_type == "weight" and entry.weight_kg is not None:
        return f"{entry.entry_label} - {entry.weight_kg:.1f} kg"
    if entry.entry_type == "waist" and entry.waist_cm is not None:
        return f"{entry.entry_label} - {entry.waist_cm:.1f} cm"

    macro_text = (
        f"{round(entry.carbs_g or 0)} g W / "
        f"{round(entry.fat_g or 0)} g T / "
        f"{round(entry.protein_g or 0)} g B"
    )
    return f"{entry.entry_label} - {round(entry.kcal or 0)} kcal | {macro_text}"


def format_day_overview(day_log: DayLog, entries: list[DayEntry]) -> str:
    if not entries:
        return (
            "Brak wpisow dla wybranego dnia. "
            f"Suma: {round(day_log.total_kcal)} kcal / cel {round(day_log.daily_kcal_target_snapshot)} kcal."
        )

    lines = ["Dzisiejsze pozycje:"]
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. {format_entry_summary(entry)}")
    if day_log.balance_mode:
        lines.append("Aktywny jest Bilans dnia - zastępuje sumę posilkow dla tego dnia.")
    lines.append(
        "Suma: "
        f"{round(day_log.total_kcal)} kcal / cel {round(day_log.daily_kcal_target_snapshot)} kcal | "
        f"W {round(day_log.total_carbs_g)} g | T {round(day_log.total_fat_g)} g | B {round(day_log.total_protein_g)} g."
    )
    return "\n".join(lines)


def help_text() -> str:
    return (
        "Uzywaj gotowych szablonow wiadomosci. Dostepne typy wpisow: Waga, Obwod pasa, Sniadanie, Obiad, "
        "Kolacja, Przekaska, Bilans dnia. Opcjonalnie dodaj pierwsza linie 'Data: YYYY-MM-DD'.\n\n"
        "Przyklad:\n"
        "Data: 2026-08-03\n"
        "Sniadanie\n"
        "Ilosc kalorii: 540\n"
        "Weglowodany: 48\n"
        "Tluszcze: 18\n"
        "Bialko: 32"
    )
