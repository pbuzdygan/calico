import sqlite3

from .conftest import PIN, meal

PROFILE = {
    "sex": "female",
    "age": 41,
    "height_cm": 168,
    "weight_kg": 74.5,
    "activity_level": "light",
    "goal_type": "cut",
    "goal_delta_pct": 0.1,
}


def test_fresh_install_has_no_users(client):
    """D10: brak uzytkownika domyslnego i PIN-u domyslnego - pierwszy start wymaga utworzenia uzytkownika."""
    assert client.get("/api/users").json() == []


def test_new_install_user_has_no_default_profile(fresh_api):
    profile = fresh_api.profile()
    assert profile["is_complete"] is False
    for field in ("sex", "age", "height_cm", "weight_kg", "activity_level", "goal_type", "daily_kcal_target"):
        assert profile[field] is None


def test_created_user_has_no_default_profile(client):
    user = client.post("/api/users", json={"display_name": "Nowa Osoba", "pin": "2468"}).json()
    profile = client.get(f"/api/profile/{user['id']}", headers={"X-User-PIN": "2468"}).json()
    assert profile["is_complete"] is False and profile["weight_kg"] is None


def test_data_endpoints_require_complete_profile(fresh_api):
    today = "2026-06-15"
    checks = [
        fresh_api.get("/api/days/current"),
        fresh_api.get("/api/days"),
        fresh_api.get(f"/api/days/{today}"),
        fresh_api.post(f"/api/days/{today}/entries", json={"entry_type": "weight", "weight_kg": 80}),
        fresh_api.get("/api/reports/summary"),
        fresh_api.get("/api/export"),
        fresh_api.client.get(f"/api/profile/{fresh_api.uid}/plan", headers=PIN),
        fresh_api.client.post("/api/chat/message", json={"user_id": fresh_api.uid, "message": meal()}, headers=PIN),
    ]
    for response in checks:
        assert response.status_code == 428, response.request.url
        assert "Uzupełnij profil" in response.json()["detail"]
    # PIN i usuniecie konta dzialaja bez profilu
    assert fresh_api.client.post(f"/api/users/{fresh_api.uid}/pin", json={"new_pin": "1234"}, headers=PIN).status_code == 200


def test_profile_requires_all_fields(fresh_api):
    for field in PROFILE:
        payload = {key: value for key, value in PROFILE.items() if key != field}
        response = fresh_api.client.put(f"/api/profile/{fresh_api.uid}", json=payload, headers=PIN)
        assert response.status_code == 422, field


def test_completing_profile_unlocks_app(fresh_api):
    response = fresh_api.client.put(f"/api/profile/{fresh_api.uid}", json=PROFILE, headers=PIN)
    assert response.status_code == 200
    profile = response.json()
    assert profile["is_complete"] is True and profile["sex"] == "female" and profile["weight_kg"] == 74.5
    assert profile["daily_kcal_target"] > 0
    day = fresh_api.day("2026-06-15")
    assert [(entry["entry_type"], entry["weight_kg"]) for entry in day["entries"]] == [("weight", 74.5)]
    assert fresh_api.chat(meal())["kind"] == "saved"


def test_migration_marks_never_saved_profiles_incomplete(client, fresh_api):
    """Profile z wartosciami domyslnymi (updated_at == created_at) sa niekompletne; zapisane pozniej - kompletne."""
    import os

    from app.db import _migration_4_profile_completion, SessionLocal

    other = client.post("/api/users", json={"display_name": "Zapisany Profil", "pin": "1357"}).json()
    con = sqlite3.connect(os.environ["SQLITE_PATH"])
    con.execute(
        "INSERT INTO profiles (user_id, sex, age, height_cm, weight_kg, activity_level, goal_type, goal_delta_pct, daily_kcal_target, updated_at) "
        "SELECT id, 'male', 30, 175, 80, 'moderate', 'maintain', 0, 2400, created_at FROM users WHERE id = ?",
        (fresh_api.uid,),
    )
    con.execute(
        "INSERT INTO profiles (user_id, sex, age, height_cm, weight_kg, activity_level, goal_type, goal_delta_pct, daily_kcal_target, updated_at) "
        "SELECT id, 'female', 35, 165, 70, 'light', 'cut', 0.1, 1800, datetime(created_at, '+2 days') FROM users WHERE id = ?",
        (other["id"],),
    )
    con.commit()
    con.close()
    with SessionLocal() as db:
        _migration_4_profile_completion(db)
        db.commit()
    assert fresh_api.profile()["is_complete"] is False
    saved = client.get(f"/api/profile/{other['id']}", headers={"X-User-PIN": "1357"}).json()
    assert saved["is_complete"] is True and saved["weight_kg"] == 70


def test_profile_preview_shows_direction_of_goal(fresh_api):
    url = f"/api/profile/{fresh_api.uid}/preview"
    base = {**PROFILE, "sex": "male", "age": 30, "height_cm": 180, "weight_kg": 100, "activity_level": "moderate"}
    cut = fresh_api.client.post(url, json={**base, "goal_type": "cut", "goal_delta_pct": 0.15}, headers=PIN).json()
    bulk = fresh_api.client.post(url, json={**base, "goal_type": "bulk", "goal_delta_pct": 0.10}, headers=PIN).json()
    keep = fresh_api.client.post(url, json={**base, "goal_type": "maintain", "goal_delta_pct": 0.0}, headers=PIN).json()
    assert cut["tdee_kcal"] == bulk["tdee_kcal"] == keep["tdee_kcal"] == 3069
    assert cut["delta_kcal"] < 0 and cut["target_kcal"] == round(3069 * 0.85)
    assert bulk["delta_kcal"] > 0 and bulk["target_kcal"] == round(3069 * 1.10)
    assert keep["delta_kcal"] == 0
    assert fresh_api.profile()["is_complete"] is False  # podglad niczego nie zapisuje
