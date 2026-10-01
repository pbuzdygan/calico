"""T2.7: waga docelowa (opcjonalna) i prognoza daty jej osiagniecia z trendu masy."""

from datetime import date, timedelta

from .conftest import PIN
from .test_plan import PLAN_START, log_weights, plan_status, set_today, start_cut_plan


def set_target_weight(api, value):
    response = api.client.put(f"/api/profile/{api.uid}/target-weight", json={"target_weight_kg": value}, headers=PIN)
    return response


def test_target_weight_is_optional(api):
    assert api.profile()["target_weight_kg"] is None
    status = plan_status(api)
    assert status["target_weight_kg"] is None and status["forecast_date"] is None and status["forecast_message"] is None


def test_set_and_clear_target_weight_without_touching_plan(api, frozen_clock):
    profile = start_cut_plan(api, frozen_clock)
    set_today(frozen_clock, PLAN_START + timedelta(days=5))
    response = set_target_weight(api, 85.5)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["target_weight_kg"] == 85.5
    # D2b: waga docelowa nie zmienia celu kcal ani startu planu
    assert saved["daily_kcal_target"] == profile["daily_kcal_target"]
    assert saved["plan_started_on"] == profile["plan_started_on"]
    assert set_target_weight(api, None).json()["target_weight_kg"] is None


def test_target_weight_validation(api):
    for value in (10, 500, "dużo"):
        assert set_target_weight(api, value).status_code == 422, value


def test_target_weight_requires_profile(fresh_api):
    assert set_target_weight(fresh_api, 80).status_code == 428


def test_forecast_from_trend(api, frozen_clock):
    start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=-0.5, days=28)  # dzis = PLAN_START + 28
    set_target_weight(api, 90)
    status = plan_status(api)
    assert status["forecast_basis"] == "trend"
    remaining = status["target_weight_remaining_kg"]
    assert -8.5 < remaining < -7.0
    weeks = remaining / status["observed_rate_kg_per_week"]
    expected = date(2026, 5, 29) + timedelta(days=round(weeks * 7))
    assert abs((date.fromisoformat(status["forecast_date"]) - expected).days) <= 1
    assert "trend" in status["forecast_message"]


def test_forecast_falls_back_to_plan_rate_without_trend(api, frozen_clock):
    start_cut_plan(api, frozen_clock)  # tylko pomiar startowy - brak trendu
    set_target_weight(api, 95)
    status = plan_status(api)
    assert status["forecast_basis"] == "plan"
    assert status["forecast_date"] is not None
    assert "planu" in status["forecast_message"]


def test_no_forecast_when_trend_goes_the_other_way(api, frozen_clock):
    start_cut_plan(api, frozen_clock)
    log_weights(api, frozen_clock, rate_per_week=0.3, days=28)
    set_target_weight(api, 90)
    status = plan_status(api)
    assert status["forecast_date"] is None and status["forecast_basis"] == "trend"
    assert "nie prowadzi" in status["forecast_message"]


def test_target_reached(api, frozen_clock):
    start_cut_plan(api, frozen_clock)
    set_target_weight(api, 100.2)
    status = plan_status(api)
    assert status["forecast_date"] is None
    assert "osiągnięta" in status["forecast_message"]
