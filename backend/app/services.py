import csv
import io
import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from slugify import slugify
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, selectinload

from . import clock
from .config import settings
from .i18n import get_language, t, use_language
from .models import AppMeta, DayEntry, DayLog, Profile, User
from .schemas import (
    DayDetailOut,
    DayEntryOut,
    DayTotalsOut,
    EntryValuesIn,
    ImportResultOut,
    ImportRowErrorOut,
    MacroTargetsIn,
    MacroTargetsOut,
    ProfileIn,
    ReportDayOut,
    ReportSummaryOut,
)
from .security import create_session_token, hash_pin, new_secret, pin_fingerprint, read_session_token, validate_pin, verify_pin


class InputError(ValueError):
    """Niepoprawne dane wejsciowe (HTTP 422)."""


class ConflictError(ValueError):
    """Operacja koliduje z istniejacymi danymi (HTTP 409)."""


class ForbiddenError(PermissionError):
    """Operacja wylaczona konfiguracja (HTTP 403)."""


class PinLockedError(Exception):
    """Za duzo blednych PIN-ow (HTTP 429)."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        minutes = max(1, -(-retry_after_seconds // 60))
        super().__init__(t("Za dużo błędnych prób PIN-u. Spróbuj ponownie za {minutes} min.", minutes=minutes))


class NotFoundError(LookupError):
    """Brak obiektu (HTTP 404)."""


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

# T3.1 / SEC-01: blokada po blednych PIN-ach - co PIN_MAX_ATTEMPTS bledow blokada 5, 10, 20, 40, 60, 60... min.
PIN_MAX_ATTEMPTS = 5
PIN_LOCK_BASE_MINUTES = 5
PIN_LOCK_MAX_MINUTES = 60

# T2.3: domyslny podzial celu kcal na makro (ogolne zalozenie). Bialko i tluszcz jako % energii celu,
# weglowodany = reszta energii. Recznie wpisany cel (Profile.*_target_g) zastepuje wartosc wyliczona.
MACRO_AUTO_PROTEIN_PCT = 0.25
MACRO_AUTO_FAT_PCT = 0.30
KCAL_PER_G = {"protein": 4, "fat": 9, "carbs": 4}

ACTIVITY_MULTIPLIER = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "high": 1.725,
    "athlete": 1.9,
}

ENTRY_TYPE_LABELS = {
    "weight": "Waga",
    "waist": "Obwód pasa",
    "breakfast": "Śniadanie",
    "lunch": "Obiad",
    "dinner": "Kolacja",
    "snack": "Przekąska",
    "daily_balance": "Bilans dnia",
}

MEAL_ENTRY_TYPES = {"breakfast", "lunch", "dinner", "snack"}
CALORIC_ENTRY_TYPES = MEAL_ENTRY_TYPES | {"daily_balance"}
MEASUREMENT_FIELDS = {"weight": "weight_kg", "waist": "waist_cm"}
SINGLE_ENTRY_TYPES = {"weight", "waist", "daily_balance"}
MACRO_FIELDS = ("kcal", "carbs_g", "fat_g", "protein_g")
VALUE_FIELDS = MACRO_FIELDS + ("weight_kg", "waist_cm")

# Naglowki szablonow po _normalize_text: polskie i angielskie (parser przyjmuje oba jezyki).
HEADER_MAP = {
    "waga": "weight",
    "obwod pasa": "waist",
    "sniadanie": "breakfast",
    "obiad": "lunch",
    "kolacja": "dinner",
    "przekaska": "snack",
    "bilans dnia": "daily_balance",
    "weight": "weight",
    "waist": "waist",
    "waist circumference": "waist",
    "breakfast": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "snack": "snack",
    "daily balance": "daily_balance",
}

FIELD_ALIASES = {
    "ilosc kalorii": "kcal",
    "kalorie": "kcal",
    "kcal": "kcal",
    "weglowodany": "carbs_g",
    "tluszcze": "fat_g",
    "bialko": "protein_g",
    "calories": "kcal",
    "carbs": "carbs_g",
    "carbohydrates": "carbs_g",
    "fat": "fat_g",
    "fats": "fat_g",
    "protein": "protein_g",
}

FIELD_LABELS = {
    "kcal": "Ilość kalorii",
    "carbs_g": "Węglowodany",
    "fat_g": "Tłuszcze",
    "protein_g": "Białko",
    "weight_kg": "Waga",
    "waist_cm": "Obwód pasa",
}

FIELD_UNITS = {"kcal": "kcal", "carbs_g": "g", "fat_g": "g", "protein_g": "g", "weight_kg": "kg", "waist_cm": "cm"}

VALUE_LIMITS = {
    "kcal": (0.0, 10000.0),
    "carbs_g": (0.0, 1000.0),
    "fat_g": (0.0, 1000.0),
    "protein_g": (0.0, 1000.0),
    "weight_kg": (30.0, 300.0),
    "waist_cm": (30.0, 250.0),
}

MIN_LOG_DATE = date(2000, 1, 1)
MAX_FUTURE_DAYS = 1
MAX_REPORT_DAYS = 3660
WEIGHT_TREND_WINDOW_DAYS = 7

# Rodzaj gramatyczny: m - meski, f - zenski, n - nijaki.
MEAL_GENDER = {"breakfast": "n", "lunch": "m", "dinner": "f", "snack": "f"}
ORDINALS = {
    2: {"m": "Drugi", "f": "Druga", "n": "Drugie"},
    3: {"m": "Trzeci", "f": "Trzecia", "n": "Trzecie"},
    4: {"m": "Czwarty", "f": "Czwarta", "n": "Czwarte"},
    5: {"m": "Piąty", "f": "Piąta", "n": "Piąte"},
    6: {"m": "Szósty", "f": "Szósta", "n": "Szóste"},
    7: {"m": "Siódmy", "f": "Siódma", "n": "Siódme"},
    8: {"m": "Ósmy", "f": "Ósma", "n": "Ósme"},
    9: {"m": "Dziewiąty", "f": "Dziewiąta", "n": "Dziewiąte"},
    10: {"m": "Dziesiąty", "f": "Dziesiąta", "n": "Dziesiąte"},
}

COMMAND_HELP = {"pomoc", "help", "co umiesz"}
COMMAND_SHOW_TODAY = {"pokaz dzis", "pokaz dzien", "stan dnia", "podsumuj dzien", "podsumowanie dnia", "pokaz podsumowanie", "show today", "today"}
COMMAND_UNDO = {"cofnij ostatni", "cofnij wpis", "undo", "undo last"}
DELETE_POSITION_PATTERN = re.compile(r"(?:usun(?: pozycje)?(?: nr)?|delete(?: item)?) (\d+)")
NUMBER_PATTERN = re.compile(r"^(\d+(?:[.,]\d+)?)\s*(kg|cm|kcal|g)?$", flags=re.IGNORECASE)


# --- formatowanie -----------------------------------------------------------


def fmt_number(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "-"
    text = f"{round(value, decimals):.{decimals}f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") if get_language() == "pl" else text


def fmt_date(value: date) -> str:
    return value.strftime("%d.%m.%Y" if get_language() == "pl" else "%d/%m/%Y")


# --- parser szablonow ---------------------------------------------------------


@dataclass
class ParsedEntryInput:
    entry_type: str
    log_date: date | None = None
    kcal: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    protein_g: float | None = None
    weight_kg: float | None = None
    waist_cm: float | None = None

    def values(self) -> dict[str, float | None]:
        return {field: getattr(self, field) for field in VALUE_FIELDS}


def _normalize_text(raw: str) -> str:
    token = raw.strip().lower().translate(POLISH_TRANSLATION_TABLE)
    token = unicodedata.normalize("NFKD", token)
    token = "".join(char for char in token if not unicodedata.combining(char))
    token = " ".join(token.replace("-", " ").split())
    return token


def _parse_number(raw: str, field: str) -> float:
    value = raw.strip()
    match = NUMBER_PATTERN.fullmatch(value)
    if not match:
        example = fmt_number(82.4) if field in ("weight_kg", "waist_cm") else "540"
        raise InputError(
            t("Niepoprawna wartość pola '{field}': '{value}'. Podaj liczbę nieujemną, np. {example}.", field=t(FIELD_LABELS[field]), value=value, example=example)
        )
    return float(match.group(1).replace(",", "."))


def parse_date_value(raw: str) -> date:
    value = raw.strip()
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    raise InputError(t("Niepoprawny format daty. Użyj RRRR-MM-DD, DD.MM.RRRR, DD-MM-RRRR albo DD/MM/RRRR."))


def _extract_optional_date(lines: list[str]) -> tuple[date | None, list[str]]:
    if lines and _normalize_text(lines[0]).startswith(("data:", "date:")):
        _, _, value = lines[0].partition(":")
        return parse_date_value(value), lines[1:]
    return None, lines


def _meal_template_help(entry_type: str) -> str:
    return build_source_text(entry_type, {"kcal": 540, "carbs_g": 48, "fat_g": 18, "protein_g": 32})


def parse_template_message(message: str) -> ParsedEntryInput:
    lines = [line.strip() for line in message.splitlines() if line.strip()]
    log_date, lines = _extract_optional_date(lines)
    if not lines:
        raise InputError(t("Brak treści wpisu. Użyj jednego z gotowych szablonów."))

    header_key, _, header_value = lines[0].partition(":")
    entry_type = HEADER_MAP.get(_normalize_text(header_key))
    if not entry_type:
        raise InputError(t("Nie rozpoznano typu wpisu. Użyj jednego z nagłówków: {headers}.", headers=_entry_type_names()))
    label = t(ENTRY_TYPE_LABELS[entry_type])

    if entry_type in MEASUREMENT_FIELDS:
        field = MEASUREMENT_FIELDS[entry_type]
        rest = lines[1:]
        if header_value.strip():
            raw_value = header_value
        else:
            example = f"{label}: {fmt_number(82.4)} kg" if entry_type == "weight" else f"{label}: 91 cm"
            if not rest:
                raise InputError(t("Podaj wartość w formacie '{example}'.", example=example))
            second_key, _, second_value = rest[0].partition(":")
            if HEADER_MAP.get(_normalize_text(second_key)) != entry_type or not second_value.strip():
                raise InputError(t("Podaj wartość w formacie '{example}'.", example=example))
            raw_value = second_value
            rest = rest[1:]
        if rest:
            raise InputError(t("Nieoczekiwana linia we wpisie '{label}': '{line}'.", label=label, line=rest[0]))
        parsed = ParsedEntryInput(entry_type=entry_type, log_date=log_date, **{field: _parse_number(raw_value, field)})
        validate_entry_input(parsed)
        return parsed

    if header_value.strip():
        raise InputError(
            t("Nagłówek '{label}' zapisz w osobnej linii, a wartości w kolejnych liniach:\n\n{example}", label=label, example=_meal_template_help(entry_type))
        )

    values: dict[str, float] = {}
    for line in lines[1:]:
        if ":" not in line:
            raise InputError(t("Niepoprawna linia: '{line}'. Każda wartość musi mieć format 'Pole: liczba'.", line=line))
        key, _, raw_value = line.partition(":")
        alias = FIELD_ALIASES.get(_normalize_text(key))
        if not alias:
            fields = ", ".join(t(FIELD_LABELS[field]) for field in MACRO_FIELDS)
            raise InputError(t("Nieznane pole '{field}'. Użyj: {fields}.", field=key.strip(), fields=fields))
        if alias in values:
            raise InputError(t("Pole '{field}' podano więcej niż raz.", field=t(FIELD_LABELS[alias])))
        if not raw_value.strip():
            raise InputError(t("Brak wartości dla pola '{field}'.", field=t(FIELD_LABELS[alias])))
        values[alias] = _parse_number(raw_value, alias)

    missing = [field for field in MACRO_FIELDS if field not in values]
    if missing:
        missing_labels = ", ".join(t(FIELD_LABELS[field]) for field in missing)
        raise InputError(t("Brakuje pól: {fields}. Wzór:\n\n{example}", fields=missing_labels, example=_meal_template_help(entry_type)))

    parsed = ParsedEntryInput(entry_type=entry_type, log_date=log_date, **values)
    validate_entry_input(parsed)
    return parsed


def entry_input_from_values(payload: EntryValuesIn, log_date: date | None = None) -> ParsedEntryInput:
    required = (MEASUREMENT_FIELDS[payload.entry_type],) if payload.entry_type in MEASUREMENT_FIELDS else MACRO_FIELDS
    values = {field: getattr(payload, field) for field in required}
    missing = [t(FIELD_LABELS[field]) for field, value in values.items() if value is None]
    if missing:
        raise InputError(t("Brakuje pól: {fields}.", fields=", ".join(missing)))
    parsed = ParsedEntryInput(entry_type=payload.entry_type, log_date=log_date, **values)
    validate_entry_input(parsed)
    return parsed


def validate_log_date(value: date) -> None:
    latest = clock.today() + timedelta(days=MAX_FUTURE_DAYS)
    if value < MIN_LOG_DATE:
        raise InputError(
            t("Data {date} jest zbyt odległa. Najwcześniejsza dozwolona data to {earliest}.", date=fmt_date(value), earliest=fmt_date(MIN_LOG_DATE))
        )
    if value > latest:
        raise InputError(t("Data {date} jest z przyszłości. Najpóźniejsza dozwolona data to {latest}.", date=fmt_date(value), latest=fmt_date(latest)))


def validate_entry_input(payload: ParsedEntryInput) -> None:
    for field, value in payload.values().items():
        if value is None:
            continue
        low, high = VALUE_LIMITS[field]
        if not low <= value <= high:
            unit = FIELD_UNITS[field]
            raise InputError(
                t(
                    "Wartość pola '{field}' ({value} {unit}) jest poza zakresem {low}-{high} {unit}.",
                    field=t(FIELD_LABELS[field]),
                    value=fmt_number(value),
                    unit=unit,
                    low=fmt_number(low),
                    high=fmt_number(high),
                )
            )
    if payload.log_date is not None:
        validate_log_date(payload.log_date)


def build_source_text(entry_type: str, values: dict[str, float | None]) -> str:
    """Tekst szablonu w jezyku zadania (podpowiedzi, odpowiedzi API)."""
    label = t(ENTRY_TYPE_LABELS[entry_type])
    if entry_type in MEASUREMENT_FIELDS:
        field = MEASUREMENT_FIELDS[entry_type]
        return f"{label}: {fmt_number(values.get(field))} {FIELD_UNITS[field]}"
    lines = [label] + [f"{t(FIELD_LABELS[field])}: {fmt_number(values.get(field))}" for field in MACRO_FIELDS]
    return "\n".join(lines)


def build_source_text_for_entry(entry: DayEntry) -> str:
    return build_source_text(entry.entry_type, {field: getattr(entry, field) for field in VALUE_FIELDS})


def canonical_source_text(entry_type: str, values: dict[str, float | None]) -> str:
    """source_text zapisywany w bazie zawsze po polsku (niezaleznie od jezyka zadania)."""
    with use_language("pl"):
        return build_source_text(entry_type, values)


def _entry_type_names() -> str:
    return ", ".join(t(ENTRY_TYPE_LABELS[entry_type]) for entry_type in ENTRY_TYPE_LABELS)


# --- profil i cel kcal --------------------------------------------------------


def calculate_bmr(profile, weight_kg: float | None = None) -> float:
    """Mifflin-St Jeor. weight_kg pozwala policzyc BMR dla innej masy niz waga planu."""
    weight = profile.weight_kg if weight_kg is None else weight_kg
    sex_factor = 5 if profile.sex == "male" else -161
    return 10 * weight + 6.25 * profile.height_cm - 5 * profile.age + sex_factor


def calculate_tdee(profile, weight_kg: float | None = None) -> float:
    return round(calculate_bmr(profile, weight_kg) * ACTIVITY_MULTIPLIER[profile.activity_level], 0)


def calculate_target(profile) -> float:
    tdee = calculate_tdee(profile)
    if profile.goal_type == "cut":
        tdee = tdee * (1 - profile.goal_delta_pct)
    elif profile.goal_type == "bulk":
        tdee = tdee * (1 + profile.goal_delta_pct)
    return round(tdee, 0)


def macro_targets(
    target_kcal: float, protein_g: float | None = None, fat_g: float | None = None, carbs_g: float | None = None
) -> dict[str, float]:
    """Cele makro (g) dla celu kcal. Pola podane recznie maja pierwszenstwo; weglowodany domyslnie dopelniaja energie."""
    protein = protein_g if protein_g is not None else round(target_kcal * MACRO_AUTO_PROTEIN_PCT / KCAL_PER_G["protein"])
    fat = fat_g if fat_g is not None else round(target_kcal * MACRO_AUTO_FAT_PCT / KCAL_PER_G["fat"])
    if carbs_g is None:
        remaining_kcal = target_kcal - protein * KCAL_PER_G["protein"] - fat * KCAL_PER_G["fat"]
        carbs_g = max(0, round(remaining_kcal / KCAL_PER_G["carbs"]))
    return {"protein_g": round(protein, 1), "fat_g": round(fat, 1), "carbs_g": round(carbs_g, 1)}


def profile_macro_targets(profile: Profile, target_kcal: float | None = None) -> dict[str, float]:
    kcal = profile.daily_kcal_target if target_kcal is None else target_kcal
    return macro_targets(kcal, profile.protein_target_g, profile.fat_target_g, profile.carbs_target_g)


def macro_targets_out(profile: Profile) -> MacroTargetsOut:
    return MacroTargetsOut(
        kcal_target=profile.daily_kcal_target,
        **profile_macro_targets(profile),
        manual_protein_g=profile.protein_target_g,
        manual_fat_g=profile.fat_target_g,
        manual_carbs_g=profile.carbs_target_g,
    )


def set_macro_targets(db: Session, profile: Profile, payload: MacroTargetsIn) -> None:
    """Reczne cele makro sa opcjonalne i nie zmieniaja planu kcal (D2b) - nie wolamy set_plan_target."""
    profile.protein_target_g = payload.protein_g
    profile.fat_target_g = payload.fat_g
    profile.carbs_target_g = payload.carbs_g
    db.flush()


def weights_between(db: Session, user_id: int, date_from: date, date_to: date) -> list[tuple[date, float]]:
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
    return [(log_date, weight) for log_date, weight in rows]


PLAN_START_WEIGHT_DAYS = 7


def set_plan_start(db: Session, profile: Profile, started_on: date) -> None:
    """Reczna data startu planu (np. po imporcie danych historycznych). Cel kcal i TDEE planu bez zmian (D2b).

    Waga planu = srednia pomiarow z 7 dni konczacych sie w dniu startu; bez nich - pierwszy pomiar do 7 dni
    po starcie; bez pomiarow - dotychczasowa waga planu.
    """
    if started_on > clock.today():
        raise InputError(t("Start planu nie może być w przyszłości."))
    if started_on < MIN_LOG_DATE:
        raise InputError(t("Start planu nie może być wcześniejszy niż {date}.", date=fmt_date(MIN_LOG_DATE)))
    window = PLAN_START_WEIGHT_DAYS - 1
    before = weights_between(db, profile.user_id, started_on - timedelta(days=window), started_on)
    after = weights_between(db, profile.user_id, started_on, started_on + timedelta(days=window))
    if before:
        profile.weight_kg = round(sum(weight for _, weight in before) / len(before), 1)
    elif after:
        profile.weight_kg = round(after[0][1], 1)
    profile.plan_started_on = started_on
    profile.updated_at = clock.utcnow_naive()
    db.flush()


def set_target_weight(db: Session, profile: Profile, target_weight_kg: float | None) -> None:
    """Waga docelowa sluzy tylko prognozie - nie zmienia planu kcal (D2b)."""
    profile.target_weight_kg = round(target_weight_kg, 1) if target_weight_kg is not None else None
    db.flush()


def get_profile(db: Session, user_id: int) -> Profile | None:
    return db.scalar(select(Profile).where(Profile.user_id == user_id))


def is_profile_complete(db: Session, user_id: int) -> bool:
    profile = get_profile(db, user_id)
    return profile is not None and profile.completed_at is not None


def current_target(db: Session, user_id: int) -> float:
    profile = get_profile(db, user_id)
    return profile.daily_kcal_target if profile else 0.0


def set_plan_target(db: Session, profile: Profile, target_kcal: float, plan_tdee_kcal: float) -> None:
    """Ustawia nowy cel planu i aktualizuje snapshot celu dzis i w przyszlych dniach (D3).

    Cel zmienia sie WYLACZNIE tutaj: przy jawnym zapisie profilu albo po zaakceptowaniu sugestii planu (D2b).
    """
    profile.daily_kcal_target = round(target_kcal, 0)
    profile.plan_tdee_kcal = round(plan_tdee_kcal, 0)
    profile.plan_started_on = clock.today()
    profile.updated_at = clock.utcnow_naive()
    future_days = db.scalars(select(DayLog).where(DayLog.user_id == profile.user_id, DayLog.log_date >= clock.today()))
    for day_log in future_days:
        day_log.daily_kcal_target_snapshot = profile.daily_kcal_target
    db.flush()


def latest_weight_entry(db: Session, user_id: int) -> DayEntry | None:
    return db.scalar(
        select(DayEntry)
        .join(DayLog)
        .where(DayLog.user_id == user_id, DayEntry.entry_type == "weight", DayEntry.weight_kg.is_not(None))
        .order_by(DayLog.log_date.desc(), DayEntry.updated_at.desc(), DayEntry.id.desc())
        .limit(1)
    )


def upsert_profile(db: Session, user_id: int, payload: ProfileIn) -> Profile:
    """Jawny zapis profilu = nowy plan bazowy: cel liczony wzorem z wagi podanej w profilu."""
    profile = get_profile(db, user_id)
    if not profile:
        profile = Profile(user_id=user_id)
        db.add(profile)
        previous_weight = None
    else:
        previous_weight = profile.weight_kg
    profile.sex = payload.sex
    profile.age = payload.age
    profile.height_cm = payload.height_cm
    profile.weight_kg = payload.weight_kg
    profile.activity_level = payload.activity_level
    profile.goal_type = payload.goal_type
    profile.goal_delta_pct = payload.goal_delta_pct
    if profile.completed_at is None:
        profile.completed_at = clock.utcnow_naive()
    db.flush()

    # Waga planu jest tez punktem startowym sledzenia wagi - zapisujemy ja jako dzisiejszy wpis 'Waga',
    # gdy uzytkownik ja zmienil albo nie ma jeszcze zadnego pomiaru.
    weight_changed = previous_weight is None or abs(previous_weight - payload.weight_kg) >= 1e-6
    if weight_changed or latest_weight_entry(db, user_id) is None:
        _create_entry(db, user_id, ParsedEntryInput(entry_type="weight", log_date=clock.today(), weight_kg=payload.weight_kg))

    set_plan_target(db, profile, calculate_target(profile), calculate_tdee(profile))
    return profile


# --- uzytkownicy ----------------------------------------------------------------


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.display_name)))


def signup_allowed(db: Session) -> bool:
    """ALLOW_SIGNUP=false blokuje nowe konta, ale pierwszy uzytkownik musi moc powstac (D10)."""
    return settings.allow_signup or not db.scalar(select(func.count(User.id)))


def create_user(db: Session, display_name: str, pin: str) -> User:
    if not signup_allowed(db):
        raise ForbiddenError(t("Zakładanie nowych kont jest wyłączone (ALLOW_SIGNUP=false)."))
    if not validate_pin(pin):
        raise InputError(t("PIN musi mieć 4-8 cyfr."))
    display_name = display_name.strip()
    slug_base = slugify(display_name)[:50] or "user"
    slug = slug_base
    suffix = 1
    while db.scalar(select(User).where(User.slug == slug)):
        suffix += 1
        slug = f"{slug_base}-{suffix}"
    user = User(slug=slug, display_name=display_name, pin_hash=hash_pin(pin), is_active=True)
    db.add(user)
    db.flush()
    # Bez profilu: uzytkownik musi go uzupelnic przy pierwszym logowaniu (is_profile_complete).
    return user


def _pin_lock_minutes(failed_attempts: int) -> int:
    lockouts = failed_attempts // PIN_MAX_ATTEMPTS
    return min(PIN_LOCK_BASE_MINUTES * 2 ** (lockouts - 1), PIN_LOCK_MAX_MINUTES)


def pin_attempts_left(user: User) -> int:
    return PIN_MAX_ATTEMPTS - (user.failed_pin_attempts or 0) % PIN_MAX_ATTEMPTS


def require_user_pin(db: Session, user_id: int, pin: str) -> User | None:
    """Sprawdza PIN z blokada po PIN_MAX_ATTEMPTS bledach (rosnaco do PIN_LOCK_MAX_MINUTES).

    Zwraca None przy blednym PIN-ie (licznik zwiekszony - wywolujacy musi zatwierdzic transakcje),
    rzuca PinLockedError, gdy konto jest zablokowane - nawet przy poprawnym PIN-ie.
    """
    user = db.get(User, user_id)
    if not user:
        return None
    now = clock.utcnow_naive()
    if user.pin_locked_until and user.pin_locked_until > now:
        raise PinLockedError(int((user.pin_locked_until - now).total_seconds()))
    if validate_pin(pin) and verify_pin(pin, user.pin_hash):
        user.failed_pin_attempts = 0
        user.pin_locked_until = None
        return user
    user.failed_pin_attempts = (user.failed_pin_attempts or 0) + 1
    if user.failed_pin_attempts % PIN_MAX_ATTEMPTS == 0:
        user.pin_locked_until = now + timedelta(minutes=_pin_lock_minutes(user.failed_pin_attempts))
    db.flush()
    return None


def _session_secret(db: Session) -> str:
    if settings.session_secret:
        return settings.session_secret
    meta = db.get(AppMeta, "session_secret")
    if meta is None:
        meta = AppMeta(key="session_secret", value=new_secret())
        db.add(meta)
        db.flush()
    return meta.value


def issue_session(db: Session, user: User) -> tuple[str, datetime]:
    expires_at = clock.now_utc() + timedelta(hours=settings.session_ttl_hours)
    token = create_session_token(user.id, user.pin_hash, _session_secret(db), int(expires_at.timestamp()))
    return token, expires_at


def user_from_session(db: Session, user_id: int, token: str) -> User | None:
    data = read_session_token(token, _session_secret(db), int(clock.now_utc().timestamp()))
    if not data or data.get("uid") != user_id:
        return None
    user = db.get(User, user_id)
    if not user or data.get("pv") != pin_fingerprint(user.pin_hash):
        return None
    return user


def change_user_pin(db: Session, user: User, new_pin: str) -> None:
    if not validate_pin(new_pin):
        raise InputError(t("PIN musi mieć 4-8 cyfr."))
    user.pin_hash = hash_pin(new_pin)
    db.flush()


def set_user_language(db: Session, user: User, language: str) -> None:
    user.language = language
    db.flush()


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.flush()


# --- dni ------------------------------------------------------------------------


def get_day_log(db: Session, user_id: int, log_date: date) -> DayLog | None:
    return db.scalar(select(DayLog).where(DayLog.user_id == user_id, DayLog.log_date == log_date))


def get_or_create_day_log(db: Session, user_id: int, log_date: date) -> DayLog:
    day_log = get_day_log(db, user_id=user_id, log_date=log_date)
    if day_log:
        return day_log
    day_log = DayLog(
        user_id=user_id,
        log_date=log_date,
        daily_kcal_target_snapshot=current_target(db, user_id),
        total_kcal=0.0,
        total_carbs_g=0.0,
        total_fat_g=0.0,
        total_protein_g=0.0,
        balance_mode=False,
    )
    db.add(day_log)
    db.flush()
    return day_log


def list_day_entries(db: Session, day_log: DayLog | None) -> list[DayEntry]:
    if day_log is None:
        return []
    db.flush()
    return list(
        db.scalars(select(DayEntry).where(DayEntry.day_log_id == day_log.id).order_by(DayEntry.entry_order.asc(), DayEntry.id.asc()))
    )


def _entry_meal_label(entry_type: str, count: int) -> str:
    base = ENTRY_TYPE_LABELS[entry_type]
    if count <= 1:
        return base
    ordinal = ORDINALS.get(count)
    if not ordinal:
        return f"{base} #{count}"
    return f"{base} {ordinal[MEAL_GENDER[entry_type]]}"


def _entry_ordinal(entry: DayEntry) -> int:
    """Numer kolejny posilku danego typu z kanonicznej (polskiej) etykiety, np. 'Kolacja Druga' -> 2."""
    if entry.entry_type not in MEAL_ENTRY_TYPES:
        return 1
    for count in range(2, max(ORDINALS) + 1):
        if entry.entry_label == _entry_meal_label(entry.entry_type, count):
            return count
    match = re.search(r"#(\d+)$", entry.entry_label or "")
    return int(match.group(1)) if match else 1


def display_entry_label(entry: DayEntry) -> str:
    """Etykieta w jezyku zadania. W bazie etykiety sa po polsku (kanoniczne); EN: 'Dinner 2'."""
    if get_language() == "pl":
        return entry.entry_label
    base = t(ENTRY_TYPE_LABELS[entry.entry_type])
    ordinal = _entry_ordinal(entry)
    return base if ordinal == 1 else f"{base} {ordinal}"


def refresh_day(db: Session, day_log: DayLog) -> list[DayEntry]:
    """Numeruje pozycje, nadaje etykiety i przelicza sumy dnia. Wolane po kazdej mutacji."""
    entries = list_day_entries(db, day_log)
    meal_counters = dict.fromkeys(MEAL_ENTRY_TYPES, 0)
    for index, entry in enumerate(entries, start=1):
        entry.entry_order = index
        if entry.entry_type in MEAL_ENTRY_TYPES:
            meal_counters[entry.entry_type] += 1
            entry.entry_label = _entry_meal_label(entry.entry_type, meal_counters[entry.entry_type])
        else:
            entry.entry_label = ENTRY_TYPE_LABELS[entry.entry_type]

    balance_entry = next((entry for entry in entries if entry.entry_type == "daily_balance"), None)
    sources = [balance_entry] if balance_entry else [entry for entry in entries if entry.entry_type in MEAL_ENTRY_TYPES]
    day_log.total_kcal = round(sum(entry.kcal or 0.0 for entry in sources), 1)
    day_log.total_carbs_g = round(sum(entry.carbs_g or 0.0 for entry in sources), 1)
    day_log.total_fat_g = round(sum(entry.fat_g or 0.0 for entry in sources), 1)
    day_log.total_protein_g = round(sum(entry.protein_g or 0.0 for entry in sources), 1)
    day_log.balance_mode = balance_entry is not None
    db.flush()
    return entries


def _day_macro_targets(profile: Profile | None, target_kcal: float) -> dict[str, float]:
    if profile is None or not target_kcal:
        return {}
    targets = profile_macro_targets(profile, target_kcal)
    return {f"target_{key}": value for key, value in targets.items()}


def day_totals_out(
    db: Session,
    user_id: int,
    log_date: date,
    day_log: DayLog | None = None,
    entries_count: int | None = None,
    profile: Profile | None = None,
) -> DayTotalsOut:
    """Sumy dnia bez tworzenia wiersza DayLog, gdy dzien jeszcze nie istnieje. Cele makro liczone od celu kcal dnia."""
    if profile is None:
        profile = get_profile(db, user_id)
    if day_log is None:
        day_log = get_day_log(db, user_id, log_date)
    if day_log is None:
        target = round(profile.daily_kcal_target if profile else 0.0, 1)
        return DayTotalsOut(
            user_id=user_id, log_date=log_date, total_kcal=0.0, target_kcal=target, **_day_macro_targets(profile, target)
        )
    if entries_count is None:
        entries_count = len(list_day_entries(db, day_log))
    return DayTotalsOut(
        **_day_macro_targets(profile, day_log.daily_kcal_target_snapshot),
        user_id=user_id,
        log_date=day_log.log_date,
        total_kcal=round(day_log.total_kcal, 1),
        target_kcal=round(day_log.daily_kcal_target_snapshot, 1),
        total_carbs_g=round(day_log.total_carbs_g, 1),
        total_fat_g=round(day_log.total_fat_g, 1),
        total_protein_g=round(day_log.total_protein_g, 1),
        balance_mode=bool(day_log.balance_mode),
        entries_count=entries_count,
    )


def _entry_out(entry: DayEntry, position: int) -> DayEntryOut:
    def rounded(value: float | None, digits: int = 1) -> float | None:
        return round(value, digits) if value is not None else None

    return DayEntryOut(
        id=entry.id,
        position=position,
        entry_type=entry.entry_type,
        entry_label=display_entry_label(entry),
        source_text=build_source_text_for_entry(entry),
        kcal=rounded(entry.kcal),
        carbs_g=rounded(entry.carbs_g),
        fat_g=rounded(entry.fat_g),
        protein_g=rounded(entry.protein_g),
        weight_kg=rounded(entry.weight_kg, 2),
        waist_cm=rounded(entry.waist_cm),
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def day_detail_out(db: Session, user_id: int, log_date: date) -> DayDetailOut:
    day_log = get_day_log(db, user_id, log_date)
    entries = list_day_entries(db, day_log)
    totals = day_totals_out(db, user_id, log_date, day_log=day_log, entries_count=len(entries))
    return DayDetailOut(
        **totals.model_dump(),
        entries=[_entry_out(entry, index) for index, entry in enumerate(entries, start=1)],
    )


def list_days(
    db: Session, user_id: int, limit: int = 30, date_from: date | None = None, date_to: date | None = None
) -> list[DayTotalsOut]:
    """Dni, w ktorych jest co najmniej jeden wpis (od najnowszego), opcjonalnie w zakresie dat."""
    safe_limit = min(max(limit, 1), 366)
    query = select(DayLog, func.count(DayEntry.id)).join(DayEntry, DayEntry.day_log_id == DayLog.id).where(DayLog.user_id == user_id)
    if date_from is not None:
        query = query.where(DayLog.log_date >= date_from)
    if date_to is not None:
        query = query.where(DayLog.log_date <= date_to)
    rows = db.execute(query.group_by(DayLog.id).order_by(DayLog.log_date.desc()).limit(safe_limit)).all()
    profile = get_profile(db, user_id)
    return [
        day_totals_out(db, user_id, day_log.log_date, day_log=day_log, entries_count=count, profile=profile)
        for day_log, count in rows
    ]


# --- wpisy ----------------------------------------------------------------------


def _single_entry_for_type(db: Session, day_log: DayLog, entry_type: str, exclude_entry_id: int | None = None) -> DayEntry | None:
    query = select(DayEntry).where(DayEntry.day_log_id == day_log.id, DayEntry.entry_type == entry_type)
    if exclude_entry_id is not None:
        query = query.where(DayEntry.id != exclude_entry_id)
    return db.scalar(query.order_by(DayEntry.entry_order.asc(), DayEntry.id.asc()))


def _apply_values(entry: DayEntry, payload: ParsedEntryInput) -> None:
    entry.entry_type = payload.entry_type
    for field, value in payload.values().items():
        setattr(entry, field, value)
    entry.source_text = canonical_source_text(payload.entry_type, payload.values())
    entry.updated_at = clock.utcnow_naive()


def _next_entry_order(db: Session, day_log: DayLog) -> int:
    db.flush()
    current_max = db.scalar(select(func.max(DayEntry.entry_order)).where(DayEntry.day_log_id == day_log.id))
    return (current_max or 0) + 1


def _create_entry(db: Session, user_id: int, payload: ParsedEntryInput) -> tuple[DayEntry, DayLog, bool]:
    target_date = payload.log_date or clock.today()
    validate_log_date(target_date)
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=target_date)
    replaced = False
    entry = _single_entry_for_type(db, day_log, payload.entry_type) if payload.entry_type in SINGLE_ENTRY_TYPES else None
    if entry:
        replaced = True
    else:
        entry = DayEntry(day_log_id=day_log.id, entry_order=_next_entry_order(db, day_log), entry_label="")
        db.add(entry)
    _apply_values(entry, payload)
    refresh_day(db, day_log)
    return entry, day_log, replaced


def create_entry(db: Session, user_id: int, payload: ParsedEntryInput) -> tuple[DayEntry, DayLog, bool]:
    """Dodaje wpis. Dla typow pojedynczych (Waga, Obwod pasa, Bilans dnia) nadpisuje istniejacy - replaced=True."""
    return _create_entry(db, user_id, payload)


def get_entry(db: Session, user_id: int, log_date: date, entry_id: int) -> DayEntry:
    entry = db.scalar(
        select(DayEntry).join(DayLog).where(DayLog.user_id == user_id, DayLog.log_date == log_date, DayEntry.id == entry_id)
    )
    if not entry:
        raise NotFoundError(t("Nie znaleziono pozycji."))
    return entry


def _ensure_single_slot_free(db: Session, day_log: DayLog, entry_type: str, exclude_entry_id: int | None) -> None:
    if entry_type not in SINGLE_ENTRY_TYPES:
        return
    if _single_entry_for_type(db, day_log, entry_type, exclude_entry_id=exclude_entry_id):
        raise ConflictError(
            t(
                "W dniu {date} jest już wpis '{label}'. Edytuj go zamiast tworzyć drugi.",
                date=fmt_date(day_log.log_date),
                label=t(ENTRY_TYPE_LABELS[entry_type]),
            )
        )


def update_entry(db: Session, user_id: int, entry: DayEntry, payload: ParsedEntryInput) -> DayEntry:
    day_log = entry.day_log
    _ensure_single_slot_free(db, day_log, payload.entry_type, exclude_entry_id=entry.id)
    _apply_values(entry, payload)
    refresh_day(db, day_log)
    return entry


def move_entry(db: Session, user_id: int, entry: DayEntry, target_date: date) -> DayLog:
    validate_log_date(target_date)
    source_day = entry.day_log
    if source_day.log_date == target_date:
        return source_day
    target_day = get_or_create_day_log(db, user_id=user_id, log_date=target_date)
    _ensure_single_slot_free(db, target_day, entry.entry_type, exclude_entry_id=entry.id)
    entry.day_log = target_day
    entry.entry_order = _next_entry_order(db, target_day)
    entry.updated_at = clock.utcnow_naive()
    db.flush()
    refresh_day(db, target_day)
    refresh_day(db, source_day)
    return target_day


def duplicate_entry(db: Session, user_id: int, entry: DayEntry, target_date: date | None = None) -> tuple[DayEntry, DayLog]:
    target_date = target_date or entry.day_log.log_date
    validate_log_date(target_date)
    target_day = get_or_create_day_log(db, user_id=user_id, log_date=target_date)
    _ensure_single_slot_free(db, target_day, entry.entry_type, exclude_entry_id=None)
    copy = DayEntry(day_log_id=target_day.id, entry_order=_next_entry_order(db, target_day), entry_label="")
    db.add(copy)
    payload = ParsedEntryInput(entry_type=entry.entry_type, **{field: getattr(entry, field) for field in VALUE_FIELDS})
    _apply_values(copy, payload)
    refresh_day(db, target_day)
    return copy, target_day


def _delete_entry(db: Session, user_id: int, entry: DayEntry) -> DayEntry:
    day_log = entry.day_log
    db.delete(entry)
    db.flush()
    refresh_day(db, day_log)
    return entry


def delete_entry(db: Session, user_id: int, log_date: date, entry_id: int) -> DayEntry:
    return _delete_entry(db, user_id, get_entry(db, user_id, log_date, entry_id))


def delete_entry_by_position(db: Session, user_id: int, log_date: date, position: int) -> DayEntry | None:
    entries = list_day_entries(db, get_day_log(db, user_id, log_date))
    if not 1 <= position <= len(entries):
        return None
    return _delete_entry(db, user_id, entries[position - 1])


def undo_last_entry(db: Session, user_id: int, log_date: date) -> DayEntry | None:
    """Usuwa ostatnio dodana lub zmieniona pozycje dnia."""
    day_log = get_day_log(db, user_id, log_date)
    if day_log is None:
        return None
    entry = db.scalar(
        select(DayEntry).where(DayEntry.day_log_id == day_log.id).order_by(desc(DayEntry.updated_at), desc(DayEntry.id)).limit(1)
    )
    if not entry:
        return None
    return _delete_entry(db, user_id, entry)


def clear_day(db: Session, user_id: int, log_date: date) -> int:
    day_log = get_day_log(db, user_id, log_date)
    entries = list_day_entries(db, day_log)
    for entry in entries:
        db.delete(entry)
    if day_log is not None:
        db.flush()
        refresh_day(db, day_log)
    return len(entries)


# --- raporty --------------------------------------------------------------------


def report_for_range(db: Session, user_id: int, date_from: date, date_to: date) -> ReportSummaryOut:
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    if (date_to - date_from).days + 1 > MAX_REPORT_DAYS:
        raise InputError(t("Zakres raportu może mieć najwyżej {days} dni.", days=MAX_REPORT_DAYS))

    day_logs = db.scalars(
        select(DayLog)
        .options(selectinload(DayLog.entries))
        .where(DayLog.user_id == user_id, DayLog.log_date >= date_from, DayLog.log_date <= date_to)
        .order_by(DayLog.log_date.asc())
    ).all()

    points: list[ReportDayOut] = []
    for day in day_logs:
        if not day.entries:
            continue
        weight = next((entry.weight_kg for entry in day.entries if entry.entry_type == "weight"), None)
        waist = next((entry.waist_cm for entry in day.entries if entry.entry_type == "waist"), None)
        points.append(
            ReportDayOut(
                log_date=day.log_date,
                total_kcal=round(day.total_kcal, 1),
                target_kcal=round(day.daily_kcal_target_snapshot, 1),
                total_carbs_g=round(day.total_carbs_g, 1),
                total_fat_g=round(day.total_fat_g, 1),
                total_protein_g=round(day.total_protein_g, 1),
                balance_mode=bool(day.balance_mode),
                has_food=any(entry.entry_type in CALORIC_ENTRY_TYPES for entry in day.entries),
                entries=len(day.entries),
                weight_kg=round(weight, 2) if weight is not None else None,
                waist_cm=round(waist, 1) if waist is not None else None,
            )
        )

    weight_points = [point for point in points if point.weight_kg is not None]
    for point in weight_points:
        window_start = point.log_date - timedelta(days=WEIGHT_TREND_WINDOW_DAYS - 1)
        window = [other.weight_kg for other in weight_points if window_start <= other.log_date <= point.log_date]
        point.weight_trend_kg = round(sum(window) / len(window), 2)

    food_points = [point for point in points if point.has_food]
    days_with_food = len(food_points)
    total_kcal = sum(point.total_kcal for point in food_points)
    total_target = sum(point.target_kcal for point in food_points)
    highest = max(food_points, key=lambda point: point.total_kcal, default=None)
    weight_start = weight_points[0].weight_kg if weight_points else None
    weight_end = weight_points[-1].weight_kg if weight_points else None

    return ReportSummaryOut(
        date_from=date_from,
        date_to=date_to,
        days_count=len(points),
        days_with_food=days_with_food,
        days_with_measurements=sum(1 for point in points if point.weight_kg is not None or point.waist_cm is not None),
        entries_count=sum(point.entries for point in points),
        total_kcal=round(total_kcal, 1),
        average_kcal=round(total_kcal / days_with_food, 1) if days_with_food else 0.0,
        average_target_kcal=round(total_target / days_with_food, 1) if days_with_food else 0.0,
        above_target_days=sum(1 for point in food_points if point.total_kcal > point.target_kcal),
        below_target_days=sum(1 for point in food_points if point.total_kcal < point.target_kcal),
        equal_target_days=sum(1 for point in food_points if point.total_kcal == point.target_kcal),
        highest_kcal_day=highest.log_date if highest else None,
        highest_kcal=highest.total_kcal if highest else None,
        balance_vs_target_kcal=round(total_kcal - total_target, 1),
        weight_start_kg=weight_start,
        weight_end_kg=weight_end,
        weight_change_kg=round(weight_end - weight_start, 2) if weight_points else None,
        points=points,
    )


def last_days_range(days: int) -> tuple[date, date]:
    safe_days = min(max(days, 1), 365)
    date_to = clock.today()
    return date_to - timedelta(days=safe_days - 1), date_to


def parse_month_to_range(month_value: str) -> tuple[date, date]:
    match = re.fullmatch(r"(\d{4})-(\d{2})", month_value.strip())
    if not match or not 1 <= int(match.group(2)) <= 12:
        raise InputError(t("Niepoprawny format miesiąca. Użyj RRRR-MM."))
    year, month = int(match.group(1)), int(match.group(2))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


# --- eksport --------------------------------------------------------------------


# --- eksport / import "wiersz = dzien" (D11) -----------------------------------------------------------

# Jeden format dla szablonu, eksportu i importu, UTF-8 z BOM. Naglowki w jezyku uzytkownika; PL: srednik i przecinek
# dziesietny (Excel PL), EN: przecinek i kropka. Import przyjmuje oba jezyki i oba separatory.
IO_COLUMNS = (
    ("log_date", "Data"),
    ("weight_kg", "Waga (kg)"),
    ("waist_cm", "Obwód pasa (cm)"),
    ("kcal", "Kalorie (kcal)"),
    ("protein_g", "Białko (g)"),
    ("carbs_g", "Węglowodany (g)"),
    ("fat_g", "Tłuszcze (g)"),
)
# Naglowki po _normalize_text i bez jednostek w nawiasach.
IO_HEADER_ALIASES = {
    "data": "log_date",
    "dzien": "log_date",
    "waga": "weight_kg",
    "obwod pasa": "waist_cm",
    "obwod": "waist_cm",
    "kalorie": "kcal",
    "kcal": "kcal",
    "ilosc kalorii": "kcal",
    "bialko": "protein_g",
    "weglowodany": "carbs_g",
    "wegle": "carbs_g",
    "tluszcze": "fat_g",
    "tluszcz": "fat_g",
    "date": "log_date",
    "day": "log_date",
    "weight": "weight_kg",
    "waist": "waist_cm",
    "waist circumference": "waist_cm",
    "calories": "kcal",
    "protein": "protein_g",
    "carbs": "carbs_g",
    "carbohydrates": "carbs_g",
    "fat": "fat_g",
    "fats": "fat_g",
}
IO_DELIMITER = ";"
IO_COMMENT = "#"
IO_FOOD_FIELDS = ("kcal", "protein_g", "carbs_g", "fat_g")
IMPORT_MAX_ROWS = 5000
IMPORT_MAX_ERRORS_SHOWN = 50


def _csv_document(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    delimiter = IO_DELIMITER if get_language() == "pl" else ","
    csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n").writerows(rows)
    return "\ufeff" + buffer.getvalue()


def _io_number(value: float | None, decimals: int) -> str:
    return "" if value is None else fmt_number(value, decimals)


def _io_header() -> list[str]:
    return [t(label) for _, label in IO_COLUMNS]


def import_template_csv() -> str:
    """Pusty formularz do wypelnienia; wiersze zaczynajace sie od # sa pomijane przy imporcie."""
    return _csv_document(
        [
            _io_header(),
            [t("# Przykład – jeden wiersz na dzień, puste komórki są pomijane. Wiersze zaczynające się od # są ignorowane."), "", "", "", "", "", ""],
            ["# 2026-09-01", fmt_number(91.2), "", "2150", "140", "210", "70"],
            ["# 2026-09-02", "", "102", "1980", "", "", ""],
        ]
    )


def export_days_csv(db: Session, user_id: int) -> str:
    """Wiersz = dzien: waga, obwod i sumy jedzenia dnia (posilki zsumowane, bilans dnia jak w karcie dnia)."""
    day_logs = db.scalars(
        select(DayLog).where(DayLog.user_id == user_id).options(selectinload(DayLog.entries)).order_by(DayLog.log_date.asc())
    ).all()
    rows = [_io_header()]
    for day_log in day_logs:
        if not day_log.entries:
            continue
        single = {entry.entry_type: entry for entry in day_log.entries if entry.entry_type in MEASUREMENT_FIELDS}
        weight = single.get("weight")
        waist = single.get("waist")
        row = [
            day_log.log_date.isoformat(),
            _io_number(weight.weight_kg if weight else None, 2),
            _io_number(waist.waist_cm if waist else None, 1),
        ]
        balance = [entry for entry in day_log.entries if entry.entry_type == "daily_balance"]
        sources = balance or [entry for entry in day_log.entries if entry.entry_type in MEAL_ENTRY_TYPES]
        totals = {"kcal": day_log.total_kcal, "protein_g": day_log.total_protein_g, "carbs_g": day_log.total_carbs_g, "fat_g": day_log.total_fat_g}
        for field in IO_FOOD_FIELDS:
            # Pole puste we wszystkich zrodlach (np. import samych kalorii) zostaje puste, a nie 0.
            known = any(getattr(entry, field) is not None for entry in sources)
            row.append(_io_number(totals[field], 1) if known else "")
        rows.append(row)
    return _csv_document(rows)


def _io_header_key(raw: str) -> str | None:
    name = _normalize_text(re.sub(r"\(.*?\)", "", raw))
    return IO_HEADER_ALIASES.get(name)


def _io_rows(content: str) -> list[list[str]]:
    text = content.lstrip("\ufeff")
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    if not first_line:
        raise InputError(t("Plik jest pusty."))
    try:
        delimiter = csv.Sniffer().sniff(first_line, delimiters=";,\t").delimiter
    except csv.Error:
        delimiter = IO_DELIMITER
    return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _io_columns(header: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, name in enumerate(header):
        if not name:
            continue
        key = _io_header_key(name)
        if key is None:
            expected = ", ".join(_io_header())
            raise InputError(t("Nieznana kolumna „{name}”. Dozwolone kolumny: {expected}. Pobierz szablon z aplikacji.", name=name, expected=expected))
        if key in columns:
            raise InputError(t("Kolumna „{name}” występuje w pliku więcej niż raz.", name=name))
        columns[key] = index
    if "log_date" not in columns:
        raise InputError(t("Brak kolumny „Data”. Pobierz szablon z aplikacji."))
    return columns


def _io_parse_row(values: dict[str, str]) -> tuple[date, list[ParsedEntryInput]]:
    if not values.get("log_date"):
        raise InputError(t("Brak daty."))
    log_date = parse_date_value(values["log_date"])
    validate_log_date(log_date)
    numbers = {}
    for field in VALUE_FIELDS:
        raw = values.get(field, "").replace("\u00a0", "").replace(" ", "")
        if raw:
            numbers[field] = _parse_number(raw, field)
    if any(field in numbers for field in IO_FOOD_FIELDS) and "kcal" not in numbers:
        raise InputError(t("Podano makroskładniki bez kalorii – uzupełnij kolumnę „Kalorie”."))
    entries = []
    for entry_type, field in MEASUREMENT_FIELDS.items():
        if field in numbers:
            entries.append(ParsedEntryInput(entry_type=entry_type, log_date=log_date, **{field: numbers[field]}))
    if "kcal" in numbers:
        food = {field: numbers.get(field) for field in IO_FOOD_FIELDS}
        entries.append(ParsedEntryInput(entry_type="daily_balance", log_date=log_date, **food))
    for entry in entries:
        validate_entry_input(entry)
    return log_date, entries


def import_days_csv(db: Session, user_id: int, content: str) -> ImportResultOut:
    """Import "wiersz = dzien" (D11). Najpierw walidacja calego pliku - przy bledach nic nie jest zapisywane.

    Dni, ktore maja juz wpisy, sa pomijane (ponowny import tego samego pliku niczego nie dubluje).
    Kalorie i makro trafiaja jako "Bilans dnia", waga i obwod jako osobne wpisy. Cel kcal bez zmian (D2b).
    """
    rows = _io_rows(content)
    data_rows = [(number, row) for number, row in enumerate(rows, start=1) if any(row) and not row[0].startswith(IO_COMMENT)]
    if not data_rows:
        raise InputError(t("Plik jest pusty."))
    (_, header), *data_rows = data_rows
    columns = _io_columns(header)
    if len(data_rows) > IMPORT_MAX_ROWS:
        raise InputError(t("Za dużo wierszy ({count}). Maksymalnie {max} w jednym pliku.", count=len(data_rows), max=IMPORT_MAX_ROWS))

    parsed: list[tuple[date, list[ParsedEntryInput]]] = []
    errors: list[ImportRowErrorOut] = []
    seen: dict[date, int] = {}
    for number, row in data_rows:
        values = {key: row[index] if index < len(row) else "" for key, index in columns.items()}
        try:
            log_date, entries = _io_parse_row(values)
            if not entries:
                continue
            if log_date in seen:
                raise InputError(t("Dzień {date} występuje w pliku więcej niż raz (wiersz {row}).", date=fmt_date(log_date), row=seen[log_date]))
            seen[log_date] = number
            parsed.append((log_date, entries))
        except InputError as exc:
            errors.append(ImportRowErrorOut(row=number, message=str(exc)))
    if errors:
        return ImportResultOut(errors=errors[:IMPORT_MAX_ERRORS_SHOWN], error_count=len(errors))

    result = ImportResultOut()
    for log_date, entries in parsed:
        existing = get_day_log(db, user_id, log_date)
        if existing is not None and existing.entries:
            result.skipped_dates.append(log_date)
            continue
        for entry in entries:
            create_entry(db, user_id, entry)  # konczy sie refresh_day
        result.imported_days += 1
        result.imported_entries += len(entries)
        if result.earliest_imported_date is None or log_date < result.earliest_imported_date:
            result.earliest_imported_date = log_date
    profile = get_profile(db, user_id)
    result.plan_started_on = profile.plan_started_on if profile else None
    if result.earliest_imported_date and result.plan_started_on and result.earliest_imported_date >= result.plan_started_on:
        result.earliest_imported_date = None
    return result


# --- czat -------------------------------------------------------------------------


def format_entry_summary(entry: DayEntry) -> str:
    label = display_entry_label(entry)
    if entry.entry_type == "weight":
        return f"{label} – {fmt_number(entry.weight_kg)} kg"
    if entry.entry_type == "waist":
        return f"{label} – {fmt_number(entry.waist_cm)} cm"
    macros = t("W {carbs} g · T {fat} g · B {protein} g", carbs=round(entry.carbs_g or 0), fat=round(entry.fat_g or 0), protein=round(entry.protein_g or 0))
    return f"{label} – {round(entry.kcal or 0)} kcal | {macros}"


def format_day_overview(db: Session, user_id: int, log_date: date) -> str:
    day_log = get_day_log(db, user_id, log_date)
    entries = list_day_entries(db, day_log)
    totals = day_totals_out(db, user_id, log_date, day_log=day_log, entries_count=len(entries))
    macros = t(
        "W {carbs} g · T {fat} g · B {protein} g",
        carbs=round(totals.total_carbs_g),
        fat=round(totals.total_fat_g),
        protein=round(totals.total_protein_g),
    )
    summary = t("Suma: {total} kcal / cel {target} kcal | {macros}.", total=round(totals.total_kcal), target=round(totals.target_kcal), macros=macros)
    if not entries:
        return t("Brak wpisów w dniu {date}. {summary}", date=fmt_date(log_date), summary=summary)
    lines = [t("Pozycje dnia {date}:", date=fmt_date(log_date))]
    lines += [f"{index}. {format_entry_summary(entry)}" for index, entry in enumerate(entries, start=1)]
    if totals.balance_mode:
        lines.append(t("Aktywny jest Bilans dnia – zastępuje sumę posiłków."))
    lines.append(summary)
    return "\n".join(lines)


def help_text() -> str:
    return t(
        "Używaj gotowych szablonów. Typy wpisów: {types}. Opcjonalnie dodaj pierwszą linię 'Data: RRRR-MM-DD'.\n\n"
        "Komendy: 'pokaż dziś', 'cofnij ostatni', 'usuń 2'.\n\nPrzykład:\nData: 2026-08-03\n{example}",
        types=_entry_type_names(),
        example=_meal_template_help("breakfast"),
    )


@dataclass
class ChatResult:
    kind: str  # saved | info | error
    text: str
    log_date: date


def handle_chat_message(db: Session, user_id: int, message: str) -> ChatResult:
    raw = message.strip()
    normalized = _normalize_text(raw)
    today = clock.today()

    if normalized in COMMAND_HELP:
        return ChatResult("info", help_text(), today)

    if normalized in COMMAND_SHOW_TODAY:
        return ChatResult("info", format_day_overview(db, user_id, today), today)

    if normalized in COMMAND_UNDO:
        deleted = undo_last_entry(db, user_id, today)
        if not deleted:
            return ChatResult("info", t("Brak dzisiejszych wpisów do cofnięcia."), today)
        return ChatResult("saved", t("Cofnąłem wpis: {entry}.", entry=format_entry_summary(deleted)), today)

    delete_match = DELETE_POSITION_PATTERN.fullmatch(normalized)
    if delete_match:
        position = int(delete_match.group(1))
        deleted = delete_entry_by_position(db, user_id, today, position)
        if not deleted:
            return ChatResult("error", t("Nie znalazłem dzisiejszej pozycji nr {position}. Wpisz 'pokaż dziś', aby zobaczyć numerację.", position=position), today)
        text = t("Usunąłem pozycję nr {position}: {entry}.", position=position, entry=format_entry_summary(deleted))
        return ChatResult("saved", text + "\n" + format_day_overview(db, user_id, today), today)

    try:
        parsed = parse_template_message(raw)
        entry, day_log, replaced = create_entry(db, user_id, parsed)
    except (InputError, ConflictError) as exc:
        return ChatResult("error", str(exc), parsed_date_or(today, raw))

    day_label = fmt_date(day_log.log_date)
    if entry.entry_type == "weight":
        template = (
            "Zaktualizowałem wagę dla dnia {date}: {value} kg. Cel kcal nie zmienia się automatycznie – ocenę planu znajdziesz w zakładce Cele."
            if replaced
            else "Zapisałem wagę dla dnia {date}: {value} kg. Cel kcal nie zmienia się automatycznie – ocenę planu znajdziesz w zakładce Cele."
        )
        text = t(template, date=day_label, value=fmt_number(entry.weight_kg))
    elif entry.entry_type == "waist":
        template = "Zaktualizowałem obwód pasa dla dnia {date}: {value} cm." if replaced else "Zapisałem obwód pasa dla dnia {date}: {value} cm."
        text = t(template, date=day_label, value=fmt_number(entry.waist_cm))
    else:
        template = "Zaktualizowałem wpis ({date}): {entry}" if replaced else "Zapisałem wpis ({date}): {entry}"
        text = t(template, date=day_label, entry=format_entry_summary(entry))
    if day_log.balance_mode and entry.entry_type in MEAL_ENTRY_TYPES:
        text += "\n" + t("W tym dniu jest Bilans dnia – zastępuje sumę posiłków.")
    return ChatResult("saved", text, day_log.log_date)


def parsed_date_or(fallback: date, raw: str) -> date:
    """Data z linii 'Data:' (jesli poprawna), zeby odpowiedz na blad dotyczyla wlasciwego dnia."""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    try:
        log_date, _ = _extract_optional_date(lines)
    except InputError:
        return fallback
    if log_date is None:
        return fallback
    try:
        validate_log_date(log_date)
    except InputError:
        return fallback
    return log_date
