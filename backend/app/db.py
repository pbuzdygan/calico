from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings
from .security import hash_pin

DATABASE_URL = f"sqlite:///{settings.sqlite_path}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        inspector = inspect(conn)
        user_columns = [col["name"] for col in inspector.get_columns("users")]
        if "pin_hash" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN pin_hash VARCHAR(256)"))
        missing_pin_users = conn.execute(text("SELECT id FROM users WHERE pin_hash IS NULL OR pin_hash = ''")).fetchall()
        for row in missing_pin_users:
            conn.execute(
                text("UPDATE users SET pin_hash = :pin_hash WHERE id = :id"),
                {"pin_hash": hash_pin(settings.default_user_pin), "id": row.id},
            )

        day_log_columns = [col["name"] for col in inspector.get_columns("day_logs")]
        if "total_carbs_g" not in day_log_columns:
            conn.execute(text("ALTER TABLE day_logs ADD COLUMN total_carbs_g FLOAT DEFAULT 0.0"))
        if "total_fat_g" not in day_log_columns:
            conn.execute(text("ALTER TABLE day_logs ADD COLUMN total_fat_g FLOAT DEFAULT 0.0"))
        if "total_protein_g" not in day_log_columns:
            conn.execute(text("ALTER TABLE day_logs ADD COLUMN total_protein_g FLOAT DEFAULT 0.0"))
        if "balance_mode" not in day_log_columns:
            conn.execute(text("ALTER TABLE day_logs ADD COLUMN balance_mode BOOLEAN DEFAULT 0"))

        bootstrap_done = conn.execute(
            text("SELECT value FROM app_meta WHERE key = 'default_user_bootstrapped'")
        ).scalar()
        users_count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() or 0
        if not bootstrap_done and users_count == 0:
            created_at = conn.execute(text("SELECT CURRENT_TIMESTAMP")).scalar()
            result = conn.execute(
                text(
                    """
                    INSERT INTO users (slug, display_name, pin_hash, is_active, created_at)
                    VALUES (:slug, :display_name, :pin_hash, :is_active, :created_at)
                    """
                ),
                {
                    "slug": "domyslny-uzytkownik",
                    "display_name": "Domyslny Uzytkownik",
                    "pin_hash": hash_pin(settings.default_user_pin),
                    "is_active": True,
                    "created_at": created_at,
                },
            )
            user_id = result.lastrowid
            conn.execute(
                text(
                    """
                    INSERT INTO profiles (
                        user_id, sex, age, height_cm, weight_kg, activity_level, goal_type, goal_delta_pct, daily_kcal_target, updated_at
                    ) VALUES (
                        :user_id, 'male', 30, 175, 80, 'moderate', 'maintain', 0.0, 2400, :updated_at
                    )
                    """
                ),
                {"user_id": user_id, "updated_at": created_at},
            )
            conn.execute(
                text("INSERT INTO app_meta (key, value) VALUES ('default_user_bootstrapped', '1')")
            )


def healthcheck() -> bool:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
