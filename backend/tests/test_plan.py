from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app import plan

from .conftest import AUTH

PLAN_START = date(2026, 5, 1)


def set_today(frozen_clock, day: date):
    frozen_clock["now"] = datetime(day.year, day.month, day.day, 10, 0, tzinfo=UTC)


def start_cut_plan(api, frozen_clock, weight=100.0):
    """Mezczyzna 30 l., 180 cm, umiarkowana aktywnosc, redukcja 15%: TDEE 3069, cel 2609, ~-0,42 kg/tydz."""
    set_today(frozen_clock, PLAN_START)
    return api.put_profile(weight_kg=weight, height_cm=180, age=30, goal_type="cut", goal_delta_pct=0.15)


def log_weights(api, frozen_clock, rate_per_week, days, start_weight=100.0, every=3, food_kcal=None):
    for offset in range(0, days + 1):
        day = PLAN_START + timedelta(days=offset)
        set_today(frozen_clock, day)
        if offset % every == 0 and offset > 0:
            api.chat(f"Waga: {start_weight + rate_per_week * offset / 7:.2f}")
        if food_kcal is not None:
            api.chat(f"Bilans dnia\nIlość kalorii: {food_kcal}\nWęglowodany: 1\nTłuszcze: 1\nBiałko: 1")


def plan_status(api):
    response = api.client.get(f"/api/profile/{api.uid}/plan", headers=AUTH)
    assert response.status_code == 200, response.text
    return response.json()


def test_no_measurements(api):
    status = plan_status(api)
    assert status["status"] == "no_data" and status["recommendation"] == "keep"


def test_on_track_keeps_target_even_though_estimated_tdee_dropped(api, frozen_clock):
    profile = start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=-0.5, days=28)
    status = plan_status(api)
    assert status["status"] == "on_track"
    assert status["recommendation"] == "keep" and status["suggested_target_kcal"] is None
    assert status["daily_kcal_target"] == profile["daily_kcal_target"]
    assert status["estimated_tdee_kcal"] < status["plan_tdee_kcal"]
    assert any("spadło" in note for note in status["notes"])
    assert status["reevaluation_due"] is True
    assert -0.6 < status["observed_rate_kg_per_week"] < -0.4


def test_stall_suggests_small_decrease_without_intake_data(api, frozen_clock):
    profile = start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=-0.05, days=30)
    status = plan_status(api)
    assert status["status"] == "above_range" and status["recommendation"] == "decrease"
    # bez danych o spozyciu: staly, maly krok (150 kcal), zaokraglony do 10
    assert status["suggested_target_kcal"] == round((profile["daily_kcal_target"] - 150) / 10) * 10
    assert status["observed_tdee_kcal"] is None
    assert "Redukcja zwolniła" in status["message"]


def test_stall_with_intake_uses_observed_tdee_and_caps_step(api, frozen_clock):
    profile = start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=0.0, days=30, food_kcal=2609)
    status = plan_status(api)
    assert status["intake_coverage_pct"] == 100
    assert abs(status["observed_tdee_kcal"] - 2609) < 5
    assert status["suggested_target_kcal"] == round((profile["daily_kcal_target"] - 200) / 10) * 10


def test_too_fast_loss_suggests_increase(api, frozen_clock):
    profile = start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=-1.5, days=28)
    status = plan_status(api)
    assert status["status"] == "below_range" and status["recommendation"] == "increase"
    assert status["suggested_target_kcal"] > profile["daily_kcal_target"]
    assert "za szybko" in status["message"]


def test_young_plan_waits(api, frozen_clock):
    start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=0.0, days=16, every=2)
    status = plan_status(api)
    assert status["status"] == "wait" and status["recommendation"] == "keep"


def test_measurements_before_plan_start_are_ignored(api, frozen_clock):
    set_today(frozen_clock, PLAN_START - timedelta(days=20))
    for offset in range(0, 20, 3):
        api.chat(f"Data: {(PLAN_START - timedelta(days=20 - offset)).isoformat()}\nWaga: {110 - offset}")
    start_cut_plan(api, frozen_clock)
    set_today(frozen_clock, PLAN_START + timedelta(days=5))
    status = plan_status(api)
    assert status["status"] == "wait"
    assert status["measurements_count"] == 1


def test_apply_suggestion(api, frozen_clock):
    profile = start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=-0.05, days=30)
    status = plan_status(api)
    url = f"/api/profile/{api.uid}/plan/apply"
    assert api.client.post(url, json={"target_kcal": status["suggested_target_kcal"] + 50}, headers=AUTH).status_code == 409
    response = api.client.post(url, json={"target_kcal": status["suggested_target_kcal"]}, headers=AUTH)
    assert response.status_code == 200, response.text
    after = response.json()
    assert after["daily_kcal_target"] == status["suggested_target_kcal"]
    assert after["plan_started_on"] == "2026-05-31" and after["plan_days"] == 0
    assert after["recommendation"] == "keep"
    new_profile = api.profile()
    assert new_profile["weight_kg"] == round(status["trend_weight_kg"], 1)
    assert new_profile["daily_kcal_target"] != profile["daily_kcal_target"]
    assert api.day("2026-05-31")["target_kcal"] == status["suggested_target_kcal"]
    assert api.client.post(url, json={"target_kcal": 2000}, headers=AUTH).status_code == 409


def test_floor_is_respected():
    female = SimpleNamespace(sex="female")
    assert plan._suggest_target(female, 1250, "decrease", None, -0.5, -0.8, -0.2) == 1200
    assert plan._suggest_target(female, 1200, "decrease", None, -0.5, -0.8, -0.2) is None
    male = SimpleNamespace(sex="male")
    assert plan._suggest_target(male, 2000, "increase", None, -0.5, -0.8, -0.2) == 2150
