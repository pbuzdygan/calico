"""T-IO (D11): eksport i import w formacie "wiersz = dzien", szablon do pobrania, pomijanie zajetych dni."""

from .conftest import complete_profile_directly, meal

HEADER = "Data;Waga (kg);Obwód pasa (cm);Kalorie (kcal);Białko (g);Węglowodany (g);Tłuszcze (g)"


def csv_lines(response):
    assert response.status_code == 200, response.text
    assert "attachment" in response.headers["content-disposition"]
    assert response.text.startswith("﻿")  # BOM - Excel rozpoznaje UTF-8 i polskie znaki
    return response.text.lstrip("﻿").strip().splitlines()


def do_import(api, content):
    response = api.post("/api/import", json={"content": content})
    assert response.status_code == 200, response.text
    return response.json()


def test_template_has_header_and_commented_example(api):
    lines = csv_lines(api.get("/api/import/template"))
    assert lines[0] == HEADER
    assert all(line.startswith("#") for line in lines[1:])
    # import nietknietego szablonu niczego nie dodaje
    result = do_import(api, api.get("/api/import/template").text)
    assert result["imported_days"] == 0 and result["errors"] == []


def test_export_one_row_per_day(api):
    api.chat(meal("Śniadanie", kcal=540, carbs=48, fat=18, protein=32))
    api.chat(meal("Obiad", kcal=720, carbs=62, fat=24, protein=45))
    api.chat("Waga: 82,45")
    api.chat("Data: 2026-06-14\nObwód pasa: 101,5")
    lines = csv_lines(api.get("/api/export"))
    assert lines[0] == HEADER
    assert lines[1] == "2026-06-14;;101,5;;;;"
    # posilki zsumowane do dnia, liczby z przecinkiem dziesietnym
    assert lines[2] == "2026-06-15;82,45;;1260;77;110;42"


def test_export_import_roundtrip(api, client):
    api.chat(meal("Śniadanie", kcal=540, carbs=48, fat=18, protein=32))
    api.chat("Waga: 82,4")
    api.chat("Data: 2026-06-10\nBilans dnia\nIlość kalorii: 2100\nWęglowodany: 200\nTłuszcze: 70\nBiałko: 150")
    do_import(api, f"{HEADER}\n2026-06-08;;;1900;;;\n")  # same kalorie - makro zostaja puste
    exported = api.get("/api/export").text
    assert "2026-06-08;;;1900;;;" in exported.splitlines()

    other = client.post("/api/users", json={"display_name": "Kopia", "pin": "2468"}).json()
    complete_profile_directly(other["id"])
    copy_headers = {"X-User-PIN": "2468"}
    response = client.post(f"/api/import?user_id={other['id']}", json={"content": exported}, headers=copy_headers)
    assert response.json()["imported_days"] == 3
    reexported = client.get(f"/api/export?user_id={other['id']}", headers=copy_headers).text
    assert reexported == exported


def test_import_simple_history(api):
    content = "\n".join(
        [
            HEADER,
            "2026-06-01;91,2;;2150;140;210;70",
            "02.06.2026;;102;1980;;;",  # inny format daty, kalorie bez makro
            "2026-06-03;90,8;;;;;",  # tylko waga
            "2026-06-04;;;;;;",  # pusty dzien - pomijany
            "",
        ]
    )
    result = do_import(api, content)
    assert {key: result[key] for key in ("imported_days", "imported_entries", "skipped_dates", "errors", "error_count")} == {
        "imported_days": 3,
        "imported_entries": 5,
        "skipped_dates": [],
        "errors": [],
        "error_count": 0,
    }
    assert result["earliest_imported_date"] == "2026-06-01"  # dane sprzed startu planu (2026-06-15) -> podpowiedz
    day = api.day("2026-06-01")
    assert day["total_kcal"] == 2150 and day["total_protein_g"] == 140 and day["balance_mode"] is True
    assert sorted(entry["entry_type"] for entry in day["entries"]) == ["daily_balance", "weight"]
    day2 = api.day("2026-06-02")
    assert day2["total_kcal"] == 1980 and day2["entries"][1]["protein_g"] is None
    assert [entry["weight_kg"] for entry in api.day("2026-06-03")["entries"]] == [90.8]


def test_import_accepts_comma_delimiter_and_header_variants(api):
    content = 'data,kcal,waga,bialko\n2026-06-01,2000,"91,5",120\n'
    result = do_import(api, content)
    assert result["imported_days"] == 1, result
    day = api.day("2026-06-01")
    assert day["total_kcal"] == 2000 and day["total_protein_g"] == 120
    assert [entry["weight_kg"] for entry in day["entries"] if entry["entry_type"] == "weight"] == [91.5]


def test_import_skips_days_with_entries(api):
    api.chat(meal(date_line="2026-06-01"))
    content = f"{HEADER}\n2026-06-01;90;;2000;100;200;60\n2026-06-02;90;;2000;100;200;60\n"
    result = do_import(api, content)
    assert result["imported_days"] == 1 and result["skipped_dates"] == ["2026-06-01"]
    assert api.day("2026-06-01")["total_kcal"] == 500  # nietkniety
    # ponowny import tego samego pliku niczego nie dubluje
    again = do_import(api, content)
    assert again["imported_days"] == 0 and again["skipped_dates"] == ["2026-06-01", "2026-06-02"]


def test_import_with_errors_imports_nothing(api):
    content = "\n".join(
        [
            HEADER,
            "2026-06-01;90;;2000;100;200;60",
            "2026-13-01;90;;;;;",
            "2026-06-03;abc;;;;;",
            "2026-06-04;;;;150;;",
            "2099-01-01;90;;;;;",
            "2026-06-01;91;;;;;",
            "2026-06-06;500;;;;;",
        ]
    )
    result = do_import(api, content)
    assert result["imported_days"] == 0
    rows = {error["row"]: error["message"] for error in result["errors"]}
    assert set(rows) == {3, 4, 5, 6, 7, 8}
    assert "daty" in rows[3]
    assert "Waga" in rows[4]
    assert "Kalorie" in rows[5]
    assert "więcej niż raz" in rows[7]
    assert "zakresem" in rows[8]
    assert api.get("/api/days").json() == []


def test_import_rejects_file_without_date_column(api):
    response = api.post("/api/import", json={"content": "Waga;Kalorie\n90;2000\n"})
    assert response.status_code == 422
    assert "Data" in response.json()["detail"]


def test_import_rejects_unknown_column(api):
    response = api.post("/api/import", json={"content": "Data;Waga;Sen (h)\n2026-06-01;90;7\n"})
    assert response.status_code == 422
    assert "Sen (h)" in response.json()["detail"]


def test_import_requires_profile(fresh_api):
    assert fresh_api.post("/api/import", json={"content": HEADER}).status_code == 428


def test_import_does_not_change_plan_target(api):
    before = api.profile()["daily_kcal_target"]
    do_import(api, f"{HEADER}\n2026-06-01;70;;;;;\n")
    assert api.profile()["daily_kcal_target"] == before  # D2b
