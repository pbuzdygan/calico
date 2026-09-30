from .conftest import meal


def test_empty_and_measurement_days_are_not_counted_as_zero_kcal(api):
    for day in ["2026-06-01", "2026-06-02", "2026-06-03"]:
        api.day(day)  # sam odczyt nie moze tworzyc dnia
    api.chat("Data: 2026-06-05\nWaga: 80")
    api.chat("Data: 2026-06-04\nBilans dnia\nIlość kalorii: 2400\nWęglowodany: 1\nTłuszcze: 1\nBiałko: 1")
    report = api.get("/api/reports/range", date_from="2026-06-01", date_to="2026-06-05").json()
    assert report["days_count"] == 2
    assert report["days_with_food"] == 1
    assert report["days_with_measurements"] == 1
    assert report["average_kcal"] == 2400
    assert report["below_target_days"] + report["above_target_days"] + report["equal_target_days"] == 1


def test_report_metrics(api):
    api.chat(meal(kcal=3000, date_line="2026-06-13"))
    api.chat(meal(kcal=1000, date_line="2026-06-14"))
    report = api.get("/api/reports/summary", days=7).json()
    assert report["date_from"] == "2026-06-09" and report["date_to"] == "2026-06-15"
    assert report["highest_kcal_day"] == "2026-06-13" and report["highest_kcal"] == 3000
    target = report["average_target_kcal"]
    assert report["balance_vs_target_kcal"] == round(4000 - 2 * target, 1)
    assert report["above_target_days"] == 1 and report["below_target_days"] == 1


def test_weight_trend(api):
    api.chat("Data: 2026-06-01\nWaga: 90")
    api.chat("Data: 2026-06-05\nWaga: 88")
    api.chat("Data: 2026-06-10\nWaga: 86")
    report = api.get("/api/reports/month", month="2026-06").json()
    assert (report["weight_start_kg"], report["weight_end_kg"], report["weight_change_kg"]) == (90, 86, -4)
    trends = [point["weight_trend_kg"] for point in report["points"]]
    assert trends == [90, 89, 87]


def test_report_validation(api):
    assert api.get("/api/reports/month", month="2026-13").status_code == 422
    assert api.get("/api/reports/month", month="abc").status_code == 422
    assert api.get("/api/reports/range", date_from="1900-01-01", date_to="2100-01-01").status_code == 422
    swapped = api.get("/api/reports/range", date_from="2026-06-10", date_to="2026-06-01").json()
    assert swapped["date_from"] == "2026-06-01"
