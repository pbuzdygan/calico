import os
import sqlite3
from pathlib import Path

from app.db import Base, engine, init_db

LEGACY_SQL = Path(__file__).parent / "fixtures" / "legacy_884cafa.sql"


def test_upgrade_from_initial_alpha(client):
    """Baza z wersji 884cafa musi przejsc wszystkie migracje (regresja: ORM w migracji 3 znal kolumny z migracji 4)."""
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    con = sqlite3.connect(os.environ["SQLITE_PATH"])
    con.executescript(LEGACY_SQL.read_text())
    con.close()

    init_db()
    init_db()  # idempotencja

    con = sqlite3.connect(os.environ["SQLITE_PATH"])
    day_columns = [row[1] for row in con.execute("PRAGMA table_info(day_logs)")]
    assert "status" not in day_columns and "closed_at" not in day_columns
    assert con.execute("SELECT value FROM app_meta WHERE key = 'schema_version'").fetchone()[0] == "8"
    days = con.execute("SELECT log_date, total_kcal FROM day_logs ORDER BY log_date").fetchall()
    assert [day for day, _ in days] == ["2026-09-01", "2026-09-02"]  # pusty dzien usuniety
    labels = [row[0] for row in con.execute("SELECT entry_label FROM day_entries ORDER BY id")]
    assert labels == ["Kolacja", "Kolacja Druga", "Waga"]
    profile_columns = [row[1] for row in con.execute("PRAGMA table_info(profiles)")]
    assert {"protein_target_g", "fat_target_g", "carbs_target_g", "target_weight_kg"} <= set(profile_columns)
    assert con.execute("SELECT completed_at FROM profiles").fetchone()[0] is None  # profil domyslny -> wymuszone uzupelnienie
    con.close()

    user_id = client.get("/api/users").json()[0]["id"]
    headers = {"X-User-PIN": "1234"}
    assert client.get(f"/api/profile/{user_id}", headers=headers).json()["is_complete"] is False
    assert client.get(f"/api/days?user_id={user_id}", headers=headers).status_code == 428
