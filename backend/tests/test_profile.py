from .conftest import meal

TODAY = "2026-06-15"


def test_profile_save_creates_start_weight_entry_and_plan(api):
    profile = api.put_profile(weight_kg=90)
    entries = api.day(TODAY)["entries"]
    assert [(entry["entry_type"], entry["weight_kg"]) for entry in entries] == [("weight", 90)]
    assert profile["daily_kcal_target"] > 0
    assert profile["plan_started_on"] == TODAY
    assert profile["plan_tdee_kcal"] >= profile["daily_kcal_target"]
    assert profile["current_weight_kg"] == 90


def test_weight_entry_does_not_change_target_or_plan_weight(api):
    start = api.put_profile(weight_kg=90, goal_type="cut", goal_delta_pct=0.15)
    reply = api.chat("Data: 2026-06-16\nWaga: 86")
    assert "nie zmienia się automatycznie" in reply["reply"]
    profile = api.profile()
    assert profile["weight_kg"] == 90  # waga planu
    assert profile["current_weight_kg"] == 86  # aktualna waga widoczna w profilu
    assert profile["daily_kcal_target"] == start["daily_kcal_target"]
    assert api.day("2026-06-16")["target_kcal"] == start["daily_kcal_target"]


def test_profile_change_updates_today_and_future_but_not_past(api):
    api.chat(meal(date_line="2026-06-10"))
    api.chat(meal())
    api.chat(meal(date_line="2026-06-16"))
    past_target = api.day("2026-06-10")["target_kcal"]
    profile = api.put_profile(weight_kg=120, activity_level="high")
    assert api.day(TODAY)["target_kcal"] == profile["daily_kcal_target"]
    assert api.day("2026-06-16")["target_kcal"] == profile["daily_kcal_target"]
    assert api.day("2026-06-10")["target_kcal"] == past_target


def test_profile_save_without_weight_change_does_not_duplicate(api):
    api.put_profile(weight_kg=90)
    api.chat("Data: 2026-06-14\nWaga: 91")
    api.put_profile(weight_kg=90, age=31)
    assert len(api.day(TODAY)["entries"]) == 1
