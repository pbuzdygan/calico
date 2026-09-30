from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EntryType = Literal["weight", "waist", "breakfast", "lunch", "dinner", "snack", "daily_balance"]
ChatKind = Literal["saved", "info", "error"]


class UserCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=128)
    pin: str = Field(pattern=r"^\d{4,8}$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    display_name: str
    is_active: bool


class PinChangeIn(BaseModel):
    new_pin: str = Field(pattern=r"^\d{4,8}$")


class ProfileIn(BaseModel):
    """Wszystkie pola wymagane - profil to krytyczne dane startowe, bez wartosci domyslnych."""

    sex: Literal["male", "female"]
    age: int = Field(ge=10, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    activity_level: Literal["sedentary", "light", "moderate", "high", "athlete"]
    goal_type: Literal["cut", "maintain", "bulk"]
    goal_delta_pct: float = Field(ge=0.0, le=0.3)


class ProfileOut(BaseModel):
    """Dla niekompletnego profilu (is_complete=False) pola danych sa puste."""

    user_id: int
    is_complete: bool = False
    sex: str | None = None
    age: int | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    activity_level: str | None = None
    goal_type: str | None = None
    goal_delta_pct: float | None = None
    daily_kcal_target: float | None = None
    plan_tdee_kcal: float | None = None
    plan_started_on: date | None = None
    current_weight_kg: float | None = None
    current_weight_date: date | None = None


class ProfilePreviewOut(BaseModel):
    """Podglad celu dla danych z formularza (bez zapisu)."""

    bmr_kcal: float
    tdee_kcal: float
    target_kcal: float
    delta_kcal: float


PlanStatus = Literal["no_data", "wait", "on_track", "below_range", "above_range"]
PlanRecommendation = Literal["keep", "increase", "decrease"]


class PlanStatusOut(BaseModel):
    goal_type: str
    plan_started_on: date
    plan_days: int
    plan_weight_kg: float
    plan_tdee_kcal: float
    daily_kcal_target: float
    current_weight_kg: float | None = None
    current_weight_date: date | None = None
    trend_weight_kg: float | None = None
    weight_change_since_plan_kg: float | None = None
    weight_change_since_plan_pct: float | None = None
    estimated_tdee_kcal: float | None = None
    measurements_count: int = 0
    observed_rate_kg_per_week: float | None = None
    observed_rate_pct_per_week: float | None = None
    expected_rate_kg_per_week: float | None = None
    expected_rate_low_kg_per_week: float | None = None
    expected_rate_high_kg_per_week: float | None = None
    intake_avg_kcal: float | None = None
    intake_coverage_pct: float | None = None
    observed_tdee_kcal: float | None = None
    status: PlanStatus
    recommendation: PlanRecommendation
    suggested_target_kcal: float | None = None
    reevaluation_due: bool = False
    message: str
    notes: list[str] = Field(default_factory=list)


class PlanApplyIn(BaseModel):
    target_kcal: float


class ChatMessageIn(BaseModel):
    user_id: int
    message: str = Field(min_length=1, max_length=1500)


class AuthVerifyIn(BaseModel):
    user_id: int
    pin: str = Field(pattern=r"^\d{4,8}$")


class AdminVerifyIn(BaseModel):
    pin: str = Field(min_length=1, max_length=64)


class AuthVerifyOut(BaseModel):
    ok: bool


class AdminStatusOut(BaseModel):
    enabled: bool


class DayTotalsOut(BaseModel):
    user_id: int
    log_date: date
    total_kcal: float
    target_kcal: float
    total_carbs_g: float = 0.0
    total_fat_g: float = 0.0
    total_protein_g: float = 0.0
    balance_mode: bool = False
    entries_count: int = 0


class ChatResponseOut(DayTotalsOut):
    kind: ChatKind
    reply: str
    warnings: list[str] = Field(default_factory=list)


class DaySummaryOut(DayTotalsOut):
    pass


class EntryValuesIn(BaseModel):
    """Strukturalny wpis z formularza. Zakresy sprawdza warstwa domenowa (wspolne z parserem tekstu)."""

    entry_type: EntryType
    kcal: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    protein_g: float | None = None
    weight_kg: float | None = None
    waist_cm: float | None = None


class EntryCreateIn(EntryValuesIn):
    pass


class EntryUpdateIn(BaseModel):
    """Edycja: albo pola strukturalne (entry_type + wartosci), albo tekst szablonu."""

    source_text: str | None = Field(default=None, min_length=1, max_length=1500)
    entry: EntryValuesIn | None = None


class EntryMoveIn(BaseModel):
    target_date: date


class EntryDuplicateIn(BaseModel):
    target_date: date | None = None


class DayEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    entry_type: str
    entry_label: str
    source_text: str
    kcal: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    protein_g: float | None = None
    weight_kg: float | None = None
    waist_cm: float | None = None
    created_at: datetime
    updated_at: datetime


class DayDetailOut(DayTotalsOut):
    entries: list[DayEntryOut] = Field(default_factory=list)


class ReportDayOut(BaseModel):
    log_date: date
    total_kcal: float
    target_kcal: float
    total_carbs_g: float = 0.0
    total_fat_g: float = 0.0
    total_protein_g: float = 0.0
    balance_mode: bool = False
    has_food: bool = False
    entries: int
    weight_kg: float | None = None
    weight_trend_kg: float | None = None
    waist_cm: float | None = None


class ReportSummaryOut(BaseModel):
    date_from: date
    date_to: date
    days_count: int
    days_with_food: int
    days_with_measurements: int
    entries_count: int
    total_kcal: float
    average_kcal: float
    average_target_kcal: float
    above_target_days: int
    below_target_days: int
    equal_target_days: int
    highest_kcal_day: date | None = None
    highest_kcal: float | None = None
    balance_vs_target_kcal: float
    weight_start_kg: float | None = None
    weight_end_kg: float | None = None
    weight_change_kg: float | None = None
    points: list[ReportDayOut] = Field(default_factory=list)


class DiagnosticsUserSummaryOut(BaseModel):
    user_id: int
    display_name: str
    slug: str
    entries_count: int
    last_event_at: str | None = None
    file_name: str


class DiagnosticsLogEntryOut(BaseModel):
    timestamp: str
    user_id: int
    user_slug: str
    display_name: str
    user_message: str
    outcome: str
    response: dict | None = None
    error: str | None = None
