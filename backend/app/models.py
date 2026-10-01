from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .clock import utcnow_naive
from .db import Base


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(256), default="")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    pin_hash: Mapped[str] = mapped_column(String(256))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # T3.1: blokada po blednych PIN-ach (services.PIN_*).
    failed_pin_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    profile: Mapped["Profile"] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all,delete-orphan",
        passive_deletes=True,
    )
    day_logs: Mapped[list["DayLog"]] = relationship(
        back_populates="user",
        cascade="all,delete-orphan",
        passive_deletes=True,
    )


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    sex: Mapped[str] = mapped_column(String(16), default="male")
    age: Mapped[int] = mapped_column(Integer, default=30)
    height_cm: Mapped[float] = mapped_column(Float, default=175)
    weight_kg: Mapped[float] = mapped_column(Float, default=80)
    activity_level: Mapped[str] = mapped_column(String(32), default="moderate")
    goal_type: Mapped[str] = mapped_column(String(16), default="maintain")
    goal_delta_pct: Mapped[float] = mapped_column(Float, default=0.0)
    # weight_kg = waga planu (startowa); aktualna waga wynika z wpisow 'Waga'.
    daily_kcal_target: Mapped[float] = mapped_column(Float, default=2400)
    plan_tdee_kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    plan_started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Profil jest kompletny dopiero po pierwszym jawnym zapisie przez uzytkownika (brak danych domyslnych).
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Cele makro wpisane recznie (g); NULL = wyliczane z celu kcal (services.macro_targets).
    protein_target_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_target_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_target_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    user: Mapped["User"] = relationship(back_populates="profile", passive_deletes=True)


class DayLog(Base):
    __tablename__ = "day_logs"
    __table_args__ = (UniqueConstraint("user_id", "log_date", name="uq_day_logs_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    log_date: Mapped[date] = mapped_column(Date, index=True)
    daily_kcal_target_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    total_kcal: Mapped[float] = mapped_column(Float, default=0.0)
    total_carbs_g: Mapped[float] = mapped_column(Float, default=0.0)
    total_fat_g: Mapped[float] = mapped_column(Float, default=0.0)
    total_protein_g: Mapped[float] = mapped_column(Float, default=0.0)
    balance_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    user: Mapped["User"] = relationship(back_populates="day_logs", passive_deletes=True)
    entries: Mapped[list["DayEntry"]] = relationship(
        back_populates="day_log",
        cascade="all,delete-orphan",
        order_by="(DayEntry.entry_order, DayEntry.id)",
    )


class DayEntry(Base):
    __tablename__ = "day_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_log_id: Mapped[int] = mapped_column(ForeignKey("day_logs.id", ondelete="CASCADE"), index=True)
    entry_order: Mapped[int] = mapped_column(Integer, default=1)
    entry_type: Mapped[str] = mapped_column(String(32), index=True)
    entry_label: Mapped[str] = mapped_column(String(64))
    source_text: Mapped[str] = mapped_column(Text)
    kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    waist_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, onupdate=utcnow_naive)

    day_log: Mapped["DayLog"] = relationship(back_populates="entries")
