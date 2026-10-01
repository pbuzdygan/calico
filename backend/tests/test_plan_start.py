"""Dane historyczne a start planu: reczna data startu planu, prognoza z ostatnich pomiarow, podpowiedz po imporcie."""

from datetime import date, timedelta

from .conftest import PIN
from .test_plan import PLAN_START, plan_status, set_today, start_cut_plan

HEADER = "Data;Waga (kg);Obwód pasa (cm);Kalorie (kcal);Białko (g);Węglowodany (g);Tłuszcze (g)"


def set_plan_start(api, value):
    return api.client.put(f"/api/profile/{api.uid}/plan-start", json={"plan_started_on": value}, headers=PIN)


def history_csv(start: date, days: int, start_weight: float, rate_per_week: float, every: int = 2) -> str:
    rows = [HEADER]
    for offset in range(0, days + 1, every):
        day = start + timedelta(days=offset)
        rows.append(f"{day.isoformat()};{start_weight + rate_per_week * offset / 7:.2f};;;;;")
    return "\n".join(rows)


def import_csv(api, content):
    response = api.post("/api/import", json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def test_move_plan_start_back_uses_history(api, frozen_clock):
    """Konto zalozone dzis, dane historyczne z importu: start planu przesuniety wstecz obejmuje trend."""
    profile = start_cut_plan(api, frozen_clock)  # 2026-05-01, 100 kg
    set_today(frozen_clock, PLAN_START + timedelta(days=1))
    import_csv(api, history_csv(PLAN_START - timedelta(days=40), 39, start_weight=106, rate_per_week=-0.5))
    before = plan_status(api)
    assert before["measurements_count"] <= 2  # tylko pomiar z profilu

    response = set_plan_start(api, (PLAN_START - timedelta(days=40)).isoformat())
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["plan_started_on"] == "2026-03-22"
    assert saved["daily_kcal_target"] == profile["daily_kcal_target"]  # D2b: cel kcal bez zmian
    assert 105.5 < saved["weight_kg"] <= 106  # waga planu = srednia pomiarow z 7 dni do nowego startu

    status = plan_status(api)
    assert status["plan_days"] == 41
    assert status["measurements_count"] >= 4
    assert status["observed_rate_kg_per_week"] is not None


def test_plan_start_validation(api, frozen_clock):
    start_cut_plan(api, frozen_clock)
    tomorrow = (PLAN_START + timedelta(days=1)).isoformat()
    assert set_plan_start(api, tomorrow).status_code == 422
    assert set_plan_start(api, "1999-12-31").status_code == 422


def test_plan_start_without_measurements_keeps_plan_weight(api, frozen_clock):
    start_cut_plan(api, frozen_clock, weight=100)
    saved = set_plan_start(api, (PLAN_START - timedelta(days=60)).isoformat()).json()
    assert saved["weight_kg"] == 100


def test_plan_start_requires_profile(fresh_api):
    assert set_plan_start(fresh_api, "2026-06-01").status_code == 428


def test_forecast_uses_recent_measurements_even_before_plan_start(api, frozen_clock):
    """Prognoza wagi docelowej to informacja o trajektorii masy - liczy trend z ostatnich tygodni, niezaleznie od startu planu."""
    start_cut_plan(api, frozen_clock)
    set_today(frozen_clock, PLAN_START + timedelta(days=1))
    import_csv(api, history_csv(PLAN_START - timedelta(days=27), 26, start_weight=102, rate_per_week=-0.5))
    api.client.put(f"/api/profile/{api.uid}/target-weight", json={"target_weight_kg": 95}, headers=PIN)
    status = plan_status(api)
    assert status["observed_rate_kg_per_week"] is None  # ocena planu: za malo danych od startu planu
    assert status["forecast_basis"] == "trend"
    assert status["forecast_date"] is not None
    assert "trend" in status["forecast_message"]


def test_import_hints_plan_start_when_history_is_older(api, frozen_clock):
    start_cut_plan(api, frozen_clock)
    result = import_csv(api, history_csv(PLAN_START - timedelta(days=30), 10, start_weight=103, rate_per_week=-0.5))
    assert result["earliest_imported_date"] == "2026-04-01"
    assert result["plan_started_on"] == "2026-05-01"
    newer = import_csv(api, f"{HEADER}\n2026-05-01;;90;;;;\n")  # dzien 1.05 ma juz wpis -> pominiety
    assert newer["earliest_imported_date"] is None
