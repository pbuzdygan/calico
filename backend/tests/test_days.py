from .conftest import PIN, meal

TODAY = "2026-06-15"


def test_reads_do_not_create_days(api):
    for day in ["2026-01-01", "2026-01-02"]:
        detail = api.day(day)
        assert detail["entries"] == [] and detail["total_kcal"] == 0
    assert api.get("/api/days/current").status_code == 200
    api.chat("pomoc")
    api.chat("pokaż dziś")
    assert api.get("/api/days").json() == []


def test_totals_and_labels(api):
    api.chat(meal("Kolacja", kcal=400))
    api.chat(meal("Kolacja", kcal=300))
    api.chat(meal("Obiad", kcal=500))
    api.chat(meal("Obiad", kcal=100))
    api.chat(meal("Śniadanie", kcal=200))
    api.chat(meal("Śniadanie", kcal=200))
    api.chat(meal("Przekąska", kcal=50))
    api.chat(meal("Przekąska", kcal=50))
    detail = api.day(TODAY)
    labels = [entry["entry_label"] for entry in detail["entries"]]
    assert labels == [
        "Kolacja",
        "Kolacja Druga",
        "Obiad",
        "Obiad Drugi",
        "Śniadanie",
        "Śniadanie Drugie",
        "Przekąska",
        "Przekąska Druga",
    ]
    assert detail["total_kcal"] == 1800
    assert detail["entries_count"] == 8
    assert [entry["position"] for entry in detail["entries"]] == list(range(1, 9))


def test_daily_balance_replaces_meals(api):
    api.chat(meal("Obiad", kcal=500))
    api.chat(meal("Bilans dnia", kcal=2100, carbs=200, fat=70, protein=140))
    detail = api.day(TODAY)
    assert detail["balance_mode"] is True
    assert detail["total_kcal"] == 2100 and detail["total_protein_g"] == 140
    balance = next(entry for entry in detail["entries"] if entry["entry_type"] == "daily_balance")
    api.delete(f"/api/days/{TODAY}/entries/{balance['id']}")
    detail = api.day(TODAY)
    assert detail["balance_mode"] is False and detail["total_kcal"] == 500


def test_single_entry_types_overwrite(api):
    api.chat("Obwód pasa: 91")
    reply = api.chat("Obwód pasa: 90")
    assert reply["kind"] == "saved" and "Zaktualizowałem" in reply["reply"]
    entries = api.day(TODAY)["entries"]
    assert len(entries) == 1 and entries[0]["waist_cm"] == 90


def test_delete_command_requires_whole_message(api):
    api.chat(meal("Obiad"))
    reply = api.chat("Obiad usun 1 raz")
    assert reply["kind"] == "error"
    assert len(api.day(TODAY)["entries"]) == 1
    reply = api.chat("usuń pozycję nr 1")
    assert reply["kind"] == "saved"
    assert api.day(TODAY)["entries"] == []


def test_undo_removes_last_modified(api, frozen_clock):
    from datetime import timedelta

    api.chat("Waga: 85")
    frozen_clock["now"] += timedelta(minutes=1)
    api.chat(meal("Przekąska"))
    frozen_clock["now"] += timedelta(minutes=1)
    api.chat("Waga: 84")  # nadpisuje wage - to jest ostatnia zmiana
    reply = api.chat("cofnij ostatni")
    assert "Waga" in reply["reply"]
    assert [entry["entry_type"] for entry in api.day(TODAY)["entries"]] == ["snack"]


def test_undo_endpoint_works_on_selected_day(api):
    api.chat(meal(date_line="2026-06-10"))
    api.chat(meal())
    response = api.post("/api/days/2026-06-10/undo")
    assert response.status_code == 200 and response.json()["entries"] == []
    assert len(api.day(TODAY)["entries"]) == 1
    assert api.post("/api/days/2026-06-10/undo").status_code == 404


def test_parse_error_is_reported_as_error(api, client):
    reply = api.chat("blah")
    assert reply["kind"] == "error"
    logs = client.get(f"/api/admin/diagnostics/logs?user_id={api.uid}", headers={"X-Admin-PIN": "4321"}).json()
    assert logs[0]["outcome"] == "error"


def test_structured_create_and_update(api):
    response = api.post(f"/api/days/{TODAY}/entries", json={"entry_type": "lunch", "kcal": 600, "carbs_g": 60, "fat_g": 20, "protein_g": 40})
    assert response.status_code == 200, response.text
    entry = response.json()["entries"][0]
    assert entry["source_text"] == "Obiad\nIlość kalorii: 600\nWęglowodany: 60\nTłuszcze: 20\nBiałko: 40"

    response = api.patch(f"/api/days/{TODAY}/entries/{entry['id']}", json={"entry": {"entry_type": "dinner", "kcal": 700, "carbs_g": 1, "fat_g": 1, "protein_g": 1}})
    assert response.status_code == 200
    assert response.json()["entries"][0]["entry_label"] == "Kolacja"
    assert response.json()["total_kcal"] == 700

    response = api.patch(f"/api/days/{TODAY}/entries/{entry['id']}", json={"source_text": meal("Obiad", kcal=650)})
    assert response.json()["total_kcal"] == 650

    bad = api.post(f"/api/days/{TODAY}/entries", json={"entry_type": "lunch", "kcal": 600})
    assert bad.status_code == 422 and "Brakuje pól" in bad.json()["detail"]
    bad = api.post(f"/api/days/{TODAY}/entries", json={"entry_type": "lunch", "kcal": -1, "carbs_g": 1, "fat_g": 1, "protein_g": 1})
    assert bad.status_code == 422
    bad = api.post("/api/days/2030-01-01/entries", json={"entry_type": "waist", "waist_cm": 90})
    assert bad.status_code == 422


def test_edit_does_not_silently_delete_other_entry(api):
    api.chat("Waga: 80")
    api.chat(meal())
    lunch = next(entry for entry in api.day(TODAY)["entries"] if entry["entry_type"] == "lunch")
    response = api.patch(f"/api/days/{TODAY}/entries/{lunch['id']}", json={"source_text": "Waga: 90"})
    assert response.status_code == 409
    assert len(api.day(TODAY)["entries"]) == 2


def test_move_and_duplicate(api):
    api.chat(meal("Obiad", kcal=500))
    entry = api.day(TODAY)["entries"][0]

    response = api.post(f"/api/days/{TODAY}/entries/{entry['id']}/duplicate", json={})
    assert response.status_code == 200 and response.json()["total_kcal"] == 1000

    response = api.post(f"/api/days/{TODAY}/entries/{entry['id']}/move", json={"target_date": "2026-06-14"})
    assert response.status_code == 200
    assert response.json()["log_date"] == "2026-06-14" and response.json()["total_kcal"] == 500
    today = api.day(TODAY)
    assert today["total_kcal"] == 500 and today["entries"][0]["entry_label"] == "Obiad"

    api.chat("Waga: 80")
    api.chat("Data: 2026-06-14\nWaga: 81")
    weight = next(entry for entry in api.day(TODAY)["entries"] if entry["entry_type"] == "weight")
    conflict = api.post(f"/api/days/{TODAY}/entries/{weight['id']}/move", json={"target_date": "2026-06-14"})
    assert conflict.status_code == 409
    conflict = api.post(f"/api/days/{TODAY}/entries/{weight['id']}/duplicate", json={})
    assert conflict.status_code == 409
    too_far = api.post(f"/api/days/{TODAY}/entries/{weight['id']}/move", json={"target_date": "2026-07-01"})
    assert too_far.status_code == 422


def test_clear_day_and_days_list(api):
    api.chat(meal(date_line="2026-06-13"))
    api.chat(meal(date_line="2026-06-14"))
    api.chat(meal())
    assert [day["log_date"] for day in api.get("/api/days").json()] == [TODAY, "2026-06-14", "2026-06-13"]
    api.post("/api/days/2026-06-14/clear")
    assert [day["log_date"] for day in api.get("/api/days").json()] == [TODAY, "2026-06-13"]


def test_wrong_pin_and_other_users_entries(client, api):
    api.chat(meal())
    entry_id = api.day(TODAY)["entries"][0]["id"]
    assert client.get(f"/api/days/{TODAY}?user_id={api.uid}", headers={"X-User-PIN": "0000"}).status_code == 401
    other = client.post("/api/users", json={"display_name": "Druga Osoba", "pin": "5555"}).json()
    from .conftest import complete_profile_directly

    complete_profile_directly(other["id"])
    response = client.delete(f"/api/days/{TODAY}/entries/{entry_id}?user_id={other['id']}", headers={"X-User-PIN": "5555"})
    assert response.status_code == 404
    assert len(api.day(TODAY)["entries"]) == 1


def test_timezone_today(api, frozen_clock):
    from datetime import UTC, datetime

    # 22:30 UTC = 00:30 czasu polskiego nastepnego dnia
    frozen_clock["now"] = datetime(2026, 6, 15, 22, 30, tzinfo=UTC)
    reply = api.chat(meal())
    assert reply["log_date"] == "2026-06-16"
    assert api.client.get("/api/meta").json()["today"] == "2026-06-16"


def test_change_pin_and_delete_user(client, api):
    response = client.post(f"/api/users/{api.uid}/pin", json={"new_pin": "987654"}, headers=PIN)
    assert response.status_code == 200
    assert client.post("/api/auth/verify", json={"user_id": api.uid, "pin": "1234"}).status_code == 401
    assert client.post("/api/auth/verify", json={"user_id": api.uid, "pin": "987654"}).status_code == 200
    assert client.delete(f"/api/users/{api.uid}", headers={"X-User-PIN": "987654"}).status_code == 200
    assert client.get("/api/users").json() == []


def test_export_csv(api):
    api.chat(meal("Śniadanie", kcal=540))
    api.chat("Waga: 82,4")
    response = api.get("/api/export")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    lines = response.text.lstrip("﻿").strip().splitlines()
    assert lines[0].startswith("data,typ,etykieta,kcal")
    assert lines[1].startswith("2026-06-15,breakfast,Śniadanie,540.0")
    assert ",82.4," in lines[2]


def test_security_headers(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in response.headers["content-security-policy"]
