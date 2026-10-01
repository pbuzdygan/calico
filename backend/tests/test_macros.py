"""T2.3: cele makro w gramach - domyslnie wyliczane z celu kcal, opcjonalnie wpisane recznie."""

from app import services

from .conftest import AUTH, meal

TODAY = "2026-06-15"


def expected_auto(target_kcal):
    protein = round(target_kcal * services.MACRO_AUTO_PROTEIN_PCT / 4)
    fat = round(target_kcal * services.MACRO_AUTO_FAT_PCT / 9)
    carbs = round((target_kcal - 4 * protein - 9 * fat) / 4)
    return {"protein_g": protein, "fat_g": fat, "carbs_g": carbs}


def macros_of(profile):
    targets = profile["macro_targets"]
    return {key: targets[key] for key in ("protein_g", "fat_g", "carbs_g")}


def test_macro_targets_derived_from_kcal_target(api):
    profile = api.profile()
    assert macros_of(profile) == expected_auto(profile["daily_kcal_target"])
    targets = profile["macro_targets"]
    assert targets["manual_protein_g"] is None and targets["manual_fat_g"] is None and targets["manual_carbs_g"] is None


def test_auto_split_adds_up_to_kcal_target():
    targets = services.macro_targets(2400)
    energy = 4 * targets["protein_g"] + 9 * targets["fat_g"] + 4 * targets["carbs_g"]
    assert abs(energy - 2400) <= 10


def test_incomplete_profile_has_no_macro_targets(fresh_api):
    assert fresh_api.profile()["macro_targets"] is None


def test_manual_protein_keeps_auto_fat_and_rebalances_carbs(api):
    target = api.profile()["daily_kcal_target"]
    response = api.client.put(f"/api/profile/{api.uid}/macros", json={"protein_g": 180}, headers=AUTH)
    assert response.status_code == 200, response.text
    targets = response.json()["macro_targets"]
    auto = expected_auto(target)
    assert targets["protein_g"] == 180 and targets["manual_protein_g"] == 180
    assert targets["fat_g"] == auto["fat_g"] and targets["manual_fat_g"] is None
    assert targets["carbs_g"] == round((target - 4 * 180 - 9 * auto["fat_g"]) / 4)


def test_all_manual_targets_are_kept_as_entered(api):
    payload = {"protein_g": 150, "fat_g": 70, "carbs_g": 200}
    targets = api.client.put(f"/api/profile/{api.uid}/macros", json=payload, headers=AUTH).json()["macro_targets"]
    assert macros_of({"macro_targets": targets}) == payload


def test_carbs_never_negative(api):
    targets = api.client.put(f"/api/profile/{api.uid}/macros", json={"protein_g": 400, "fat_g": 300}, headers=AUTH).json()["macro_targets"]
    assert targets["carbs_g"] == 0


def test_clearing_manual_targets_returns_to_auto(api):
    api.client.put(f"/api/profile/{api.uid}/macros", json={"protein_g": 180, "fat_g": 60}, headers=AUTH)
    response = api.client.put(f"/api/profile/{api.uid}/macros", json={}, headers=AUTH)
    profile = response.json()
    assert macros_of(profile) == expected_auto(profile["daily_kcal_target"])


def test_macro_targets_do_not_restart_plan(api, frozen_clock):
    """D2b: zmiana celow makro nie jest nowym planem - cel kcal i start planu bez zmian."""
    from datetime import timedelta

    before = api.profile()
    frozen_clock["now"] = frozen_clock["now"] + timedelta(days=3)
    after = api.client.put(f"/api/profile/{api.uid}/macros", json={"protein_g": 160}, headers=AUTH).json()
    assert after["daily_kcal_target"] == before["daily_kcal_target"]
    assert after["plan_started_on"] == before["plan_started_on"]


def test_macro_targets_validation(api):
    for payload in ({"protein_g": -1}, {"fat_g": 5000}, {"carbs_g": "dużo"}):
        response = api.client.put(f"/api/profile/{api.uid}/macros", json=payload, headers=AUTH)
        assert response.status_code == 422, payload


def test_macro_targets_require_profile(fresh_api):
    response = fresh_api.client.put(f"/api/profile/{fresh_api.uid}/macros", json={"protein_g": 150}, headers=AUTH)
    assert response.status_code == 428


def test_day_reports_macro_targets_for_its_kcal_target(api):
    api.client.put(f"/api/profile/{api.uid}/macros", json={"protein_g": 170}, headers=AUTH)
    api.chat(meal())
    day = api.day(TODAY)
    expected = services.macro_targets(day["target_kcal"], protein_g=170)
    assert (day["target_protein_g"], day["target_fat_g"], day["target_carbs_g"]) == (
        expected["protein_g"],
        expected["fat_g"],
        expected["carbs_g"],
    )
    # dzien bez wpisow tez ma cele (bez tworzenia wiersza)
    empty = api.day("2026-06-16")
    assert empty["target_protein_g"] == 170


def test_profile_save_keeps_manual_macro_targets(api):
    api.client.put(f"/api/profile/{api.uid}/macros", json={"protein_g": 175}, headers=AUTH)
    profile = api.put_profile(weight_kg=88)
    assert profile["macro_targets"]["manual_protein_g"] == 175
