from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import settings

DATABASE_URL = f"sqlite:///{settings.sqlite_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

SCHEMA_VERSION_KEY = "schema_version"


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


def _columns(conn: Connection, table: str) -> list[str]:
    return [col["name"] for col in inspect(conn).get_columns(table)]


def _legacy_column_upgrades(conn: Connection) -> None:
    """Kolumny dodane przed wprowadzeniem wersjonowania schematu."""
    # Najstarsza wspierana baza (884cafa) ma juz PIN-y; brak PIN-u domyslnego do uzupelniania (D10).
    if "pin_hash" not in _columns(conn, "users"):
        conn.execute(text("ALTER TABLE users ADD COLUMN pin_hash VARCHAR(256)"))

    day_log_columns = _columns(conn, "day_logs")
    for column, ddl in (
        ("total_carbs_g", "FLOAT DEFAULT 0.0"),
        ("total_fat_g", "FLOAT DEFAULT 0.0"),
        ("total_protein_g", "FLOAT DEFAULT 0.0"),
        ("balance_mode", "BOOLEAN DEFAULT 0"),
    ):
        if column not in day_log_columns:
            conn.execute(text(f"ALTER TABLE day_logs ADD COLUMN {column} {ddl}"))


def _migration_1_drop_day_status(db: Session) -> None:
    """D1: status dnia (open/closed) zostal usuniety z produktu."""
    columns = _columns(db.connection(), "day_logs")
    for column in ("status", "closed_at"):
        if column in columns:
            db.execute(text(f"ALTER TABLE day_logs DROP COLUMN {column}"))


def _migration_2_normalize_days(db: Session) -> None:
    """Etykiety z polskimi znakami, kanoniczny source_text, przeliczone sumy, usuniete puste dni."""
    from . import services
    from .models import DayLog

    for day_log in db.query(DayLog).all():
        if not day_log.entries:
            db.delete(day_log)
            continue
        for entry in day_log.entries:
            entry.source_text = services.build_source_text_for_entry(entry)
        services.refresh_day(db, day_log)
    db.flush()


def _migration_3_plan_fields(db: Session) -> None:
    """D2b: cel kcal to plan (zmieniany jawnie), a nie wynik wzoru po kazdym wazeniu.

    Czysty SQL: model ORM Profile zna kolumny z pozniejszych migracji, ktorych tu jeszcze nie ma.
    """
    from types import SimpleNamespace

    from . import services

    columns = _columns(db.connection(), "profiles")
    if "plan_tdee_kcal" not in columns:
        db.execute(text("ALTER TABLE profiles ADD COLUMN plan_tdee_kcal FLOAT"))
    if "plan_started_on" not in columns:
        db.execute(text("ALTER TABLE profiles ADD COLUMN plan_started_on DATE"))
    rows = db.execute(
        text("SELECT id, sex, age, height_cm, weight_kg, activity_level, plan_tdee_kcal FROM profiles")
    ).mappings().all()
    for row in rows:
        if row["plan_tdee_kcal"] is None:
            db.execute(
                text("UPDATE profiles SET plan_tdee_kcal = :tdee WHERE id = :id"),
                {"tdee": services.calculate_tdee(SimpleNamespace(**row)), "id": row["id"]},
            )
    db.execute(
        text("UPDATE profiles SET plan_started_on = date(coalesce(updated_at, CURRENT_TIMESTAMP)) WHERE plan_started_on IS NULL")
    )


def _migration_4_profile_completion(db: Session) -> None:
    """Profil musi byc jawnie uzupelniony przez uzytkownika. Profile nigdy niezapisane (tylko wartosci
    domyslne z chwili zakladania konta) zostaja oznaczone jako niekompletne - uzytkownik uzupelni je przy logowaniu."""
    if "completed_at" not in _columns(db.connection(), "profiles"):
        db.execute(text("ALTER TABLE profiles ADD COLUMN completed_at DATETIME"))
    db.execute(
        text(
            """
            UPDATE profiles SET completed_at = updated_at
            WHERE completed_at IS NULL
              AND updated_at IS NOT NULL
              AND abs(strftime('%s', updated_at) - strftime('%s', (SELECT created_at FROM users WHERE users.id = profiles.user_id))) > 5
            """
        )
    )


def _migration_5_macro_targets(db: Session) -> None:
    """T2.3: opcjonalne, recznie wpisane cele makro w g. NULL = cel wyliczany z celu kcal."""
    columns = _columns(db.connection(), "profiles")
    for column in ("protein_target_g", "fat_target_g", "carbs_target_g"):
        if column not in columns:
            db.execute(text(f"ALTER TABLE profiles ADD COLUMN {column} FLOAT"))


def _migration_6_pin_lockout(db: Session) -> None:
    """T3.1 / SEC-01: licznik blednych PIN-ow i czas blokady per uzytkownik."""
    columns = _columns(db.connection(), "users")
    if "failed_pin_attempts" not in columns:
        db.execute(text("ALTER TABLE users ADD COLUMN failed_pin_attempts INTEGER NOT NULL DEFAULT 0"))
    if "pin_locked_until" not in columns:
        db.execute(text("ALTER TABLE users ADD COLUMN pin_locked_until DATETIME"))


def _migration_7_target_weight(db: Session) -> None:
    """T2.7: opcjonalna waga docelowa (prognoza daty osiagniecia z trendu)."""
    if "target_weight_kg" not in _columns(db.connection(), "profiles"):
        db.execute(text("ALTER TABLE profiles ADD COLUMN target_weight_kg FLOAT"))


MIGRATIONS = [
    (1, _migration_1_drop_day_status),
    (2, _migration_2_normalize_days),
    (3, _migration_3_plan_fields),
    (4, _migration_4_profile_completion),
    (5, _migration_5_macro_targets),
    (6, _migration_6_pin_lockout),
    (7, _migration_7_target_weight),
]


def _run_migrations() -> None:
    with SessionLocal() as db:
        raw_version = db.execute(text("SELECT value FROM app_meta WHERE key = :key"), {"key": SCHEMA_VERSION_KEY}).scalar()
        current = int(raw_version or 0)
        for version, migration in MIGRATIONS:
            if version <= current:
                continue
            migration(db)
            db.execute(
                text("INSERT INTO app_meta (key, value) VALUES (:key, :value) ON CONFLICT(key) DO UPDATE SET value = :value"),
                {"key": SCHEMA_VERSION_KEY, "value": str(version)},
            )
            db.commit()


def init_db() -> None:
    from . import models  # noqa: F401  rejestracja tabel w Base.metadata

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _legacy_column_upgrades(conn)
    _run_migrations()


def healthcheck() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
