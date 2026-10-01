from datetime import date

import pytest

from app.services import InputError, build_source_text, parse_template_message

from .conftest import meal


@pytest.mark.parametrize(
    "message",
    [
        "Waga: 82.4 kg",
        "Waga: 82,4",
        "Waga:\nWaga: 82.4 kg",
        "Waga\nWaga: 82,4 kg",
        "waga: 82.4KG",
    ],
)
def test_weight_formats(message):
    parsed = parse_template_message(message)
    assert parsed.entry_type == "weight"
    assert parsed.weight_kg == 82.4


@pytest.mark.parametrize("message", ["Obwód pasa: 91 cm", "Obwod pasa:\nObwod pasa: 91", "obwod-pasa: 91"])
def test_waist_formats(message):
    parsed = parse_template_message(message)
    assert parsed.entry_type == "waist"
    assert parsed.waist_cm == 91


@pytest.mark.parametrize(
    "header,entry_type",
    [
        ("Śniadanie", "breakfast"),
        ("Sniadanie", "breakfast"),
        ("Obiad", "lunch"),
        ("Kolacja", "dinner"),
        ("Przekąska", "snack"),
        ("Przekaska", "snack"),
        ("Bilans dnia", "daily_balance"),
    ],
)
def test_meal_headers(header, entry_type):
    parsed = parse_template_message(meal(header, kcal=540, carbs="48,5", fat=18, protein=32))
    assert parsed.entry_type == entry_type
    assert (parsed.kcal, parsed.carbs_g, parsed.fat_g, parsed.protein_g) == (540, 48.5, 18, 32)


def test_meal_without_diacritics_and_units():
    parsed = parse_template_message("Obiad\nIlosc kalorii: 540 kcal\nWeglowodany: 48 g\nTluszcze: 18g\nBialko: 32")
    assert parsed.kcal == 540 and parsed.fat_g == 18


@pytest.mark.parametrize(
    "date_text", ["2026-06-14", "14.06.2026", "14-06-2026", "14/06/2026"]
)
def test_date_formats(date_text):
    parsed = parse_template_message(meal(date_line=date_text))
    assert parsed.log_date == date(2026, 6, 14)


@pytest.mark.parametrize(
    "message,fragment",
    [
        ("", "Brak treści"),
        ("blah", "Nie rozpoznano typu"),
        ("Waga: -5", "Niepoprawna wartość"),
        ("Waga: abc12xyz", "Niepoprawna wartość"),
        ("Waga: 1.234,5", "Niepoprawna wartość"),
        ("Waga: 0", "poza zakresem"),
        ("Waga: 82\nObiad", "Nieoczekiwana linia"),
        ("Waga:", "Podaj wartość"),
        (meal(kcal=-5000), "Niepoprawna wartość"),
        (meal(kcal=20000), "poza zakresem"),
        (meal(protein=2000), "poza zakresem"),
        ("Obiad\nIlość kalorii: 500", "Brakuje pól"),
        ("Obiad\nIlość kalorii: 500\nIlość kalorii: 600\nWęglowodany: 1\nTłuszcze: 1\nBiałko: 1", "więcej niż raz"),
        ("Obiad\nCukier: 5", "Nieznane pole"),
        ("Obiad\nIlość kalorii 500", "Niepoprawna linia"),
        ("Obiad: 500", "osobnej linii"),
        (meal(date_line="2099-01-01"), "z przyszłości"),
        (meal(date_line="1999-12-31"), "zbyt odległa"),
        (meal(date_line="31.02.2026"), "format daty"),
    ],
)
def test_invalid_messages(message, fragment):
    with pytest.raises(InputError) as exc:
        parse_template_message(message)
    assert fragment in str(exc.value)


def test_tomorrow_is_allowed():
    assert parse_template_message(meal(date_line="2026-06-16")).log_date == date(2026, 6, 16)


def test_source_text_roundtrip():
    text = build_source_text("breakfast", {"kcal": 540, "carbs_g": 48.5, "fat_g": 18, "protein_g": 32})
    assert text == "Śniadanie\nIlość kalorii: 540\nWęglowodany: 48,5\nTłuszcze: 18\nBiałko: 32"
    parsed = parse_template_message(text)
    assert parsed.carbs_g == 48.5
    assert build_source_text("weight", {"weight_kg": 82.4}) == "Waga: 82,4 kg"
