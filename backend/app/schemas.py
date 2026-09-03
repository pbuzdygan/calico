from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=128)
    pin: str = Field(pattern=r"^\d{4,8}$")


class UserOut(BaseModel):
    id: int
    slug: str
    display_name: str
    is_active: bool

    class Config:
        from_attributes = True


class ProfileIn(BaseModel):
    sex: Literal["male", "female"] = "male"
    age: int = Field(ge=10, le=100)
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    activity_level: Literal["sedentary", "light", "moderate", "high", "athlete"] = "moderate"
    goal_type: Literal["cut", "maintain", "bulk"] = "maintain"
    goal_delta_pct: float = Field(default=0.0, ge=0.0, le=0.3)


class ProfileOut(ProfileIn):
    user_id: int
    daily_kcal_target: float

    class Config:
        from_attributes = True


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


class ChatResponseOut(BaseModel):
    reply: str
    log_date: date
    total_kcal: float
    target_kcal: float
    total_carbs_g: float = 0.0
    total_fat_g: float = 0.0
    total_protein_g: float = 0.0
    status: str
    balance_mode: bool = False
    warnings: list[str] = Field(default_factory=list)


class DaySummaryOut(BaseModel):
    user_id: int
    log_date: date
    status: str
    total_kcal: float
    target_kcal: float
    total_carbs_g: float = 0.0
    total_fat_g: float = 0.0
    total_protein_g: float = 0.0
    balance_mode: bool = False


class DayEntryUpdateIn(BaseModel):
    source_text: str = Field(min_length=1, max_length=1500)


class DayEntryMoveIn(BaseModel):
    target_date: date


class DayEntryOut(BaseModel):
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

    class Config:
        from_attributes = True


class DayDetailOut(BaseModel):
    user_id: int
    log_date: date
    status: str
    total_kcal: float
    target_kcal: float
    total_carbs_g: float = 0.0
    total_fat_g: float = 0.0
    total_protein_g: float = 0.0
    balance_mode: bool = False
    entries: list[DayEntryOut] = Field(default_factory=list)


class ReportDayOut(BaseModel):
    log_date: date
    total_kcal: float
    target_kcal: float
    total_carbs_g: float = 0.0
    total_fat_g: float = 0.0
    total_protein_g: float = 0.0
    balance_mode: bool = False
    status: str
    entries: int


class ReportSummaryOut(BaseModel):
    date_from: date
    date_to: date
    days_count: int
    entries_count: int
    total_kcal: float
    average_kcal: float
    average_target_kcal: float
    above_target_days: int
    below_target_days: int
    equal_target_days: int
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
