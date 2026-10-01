"""i18n: kazdy tekst z t("...") ma tlumaczenie EN, slownik nie ma martwych wpisow, polskie teksty nie omijaja t().

Te testy sa straznikiem tlumaczen: nowy komunikat bez wpisu w app/locales/en.py nie przejdzie CI.
"""

import ast
import re
import string
from pathlib import Path

from app.locales.en import MESSAGES

from .conftest import PIN, meal

APP = Path(__file__).resolve().parent.parent / "app"
SOURCES = [path for path in APP.glob("*.py") if path.name != "i18n.py"]
POLISH = re.compile(r"[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
# Stale z polskimi etykietami (tlumaczone przy uzyciu przez t(STALA[...])) i dane parsera.
LABEL_CONSTANTS = {"ENTRY_TYPE_LABELS", "FIELD_LABELS", "IO_COLUMNS", "ORDINALS", "POLISH_TRANSLATION_TABLE"}


def _string_args_of_t(tree: ast.AST) -> set[str]:
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "t" and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                keys.add(arg.value)
            elif isinstance(arg, ast.IfExp):  # t("a" if x else "b")
                keys |= {branch.value for branch in (arg.body, arg.orelse) if isinstance(branch, ast.Constant)}
    return keys


def _template_variables(tree: ast.AST) -> set[str]:
    """Teksty przypisane do zmiennej 'template' (potem t(template, ...))."""
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "template" for target in node.targets):
            values = [node.value.body, node.value.orelse] if isinstance(node.value, ast.IfExp) else [node.value]
            keys |= {value.value for value in values if isinstance(value, ast.Constant) and isinstance(value.value, str)}
    return keys


def _label_constants(tree: ast.AST) -> set[str]:
    keys = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) in {"ENTRY_TYPE_LABELS", "FIELD_LABELS", "IO_COLUMNS"} for target in node.targets):
            for child in ast.walk(node.value):
                if isinstance(child, ast.Constant) and isinstance(child.value, str) and child.value[:1].isupper():
                    keys.add(child.value)
    return keys


def _used_keys() -> set[str]:
    keys = set()
    for path in SOURCES:
        tree = ast.parse(path.read_text())
        keys |= _string_args_of_t(tree) | _template_variables(tree) | _label_constants(tree)
    return keys


def test_every_message_has_english_translation():
    missing = sorted(_used_keys() - set(MESSAGES))
    assert not missing, "Brak tlumaczen EN w app/locales/en.py:\n" + "\n".join(missing)


def test_no_unused_translations():
    unused = sorted(set(MESSAGES) - _used_keys())
    assert not unused, "Nieuzywane wpisy w app/locales/en.py:\n" + "\n".join(unused)


def test_placeholders_match():
    for key, value in MESSAGES.items():
        source = {name for _, name, _, _ in string.Formatter().parse(key) if name}
        target = {name for _, name, _, _ in string.Formatter().parse(value) if name}
        assert source == target, f"Rozne parametry w tlumaczeniu: {key!r} -> {value!r}"
        assert not POLISH.search(value), f"Polskie znaki w tlumaczeniu EN: {value!r}"


def test_polish_text_goes_through_t():
    """Literal z polskimi znakami poza t(), stalymi etykiet i docstringami = tekst, ktory nie zostanie przetlumaczony."""
    offenders = []
    for path in SOURCES:
        tree = ast.parse(path.read_text())
        allowed = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "t":
                allowed |= {id(child) for child in ast.walk(node)}
            if isinstance(node, ast.Assign) and any(
                getattr(target, "id", None) in LABEL_CONSTANTS | {"template"} for target in node.targets
            ):
                allowed |= {id(child) for child in ast.walk(node.value)}
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and node.body and isinstance(node.body[0], ast.Expr):
                allowed.add(id(node.body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and POLISH.search(node.value) and id(node) not in allowed:
                offenders.append(f"{path.name}:{node.lineno}: {node.value[:80]!r}")
    assert not offenders, "Polski tekst poza t():\n" + "\n".join(offenders)


# --- zachowanie API w jezyku angielskim -----------------------------------------------------------

EN = {**PIN, "Accept-Language": "en-GB,en;q=0.9"}


def test_api_messages_follow_accept_language(api):
    response = api.client.post(f"/api/days/2026-06-15/entries?user_id={api.uid}", json={"entry_type": "lunch", "kcal": 500}, headers=EN)
    assert response.status_code == 422
    assert "Missing fields" in response.json()["detail"]
    polish = api.client.post(f"/api/days/2026-06-15/entries?user_id={api.uid}", json={"entry_type": "lunch", "kcal": 500}, headers=PIN)
    assert "Brakuje pól" in polish.json()["detail"]


def test_entry_labels_and_numbers_in_english(api):
    api.chat(meal("Kolacja"))
    api.chat(meal("Kolacja", kcal=300))
    day = api.client.get(f"/api/days/2026-06-15?user_id={api.uid}", headers=EN).json()
    assert [entry["entry_label"] for entry in day["entries"]] == ["Dinner", "Dinner 2"]
    assert day["entries"][1]["source_text"].startswith("Dinner\nCalories: 300")
    # w bazie etykiety i source_text zostaja polskie (kanoniczne)
    assert [entry["entry_label"] for entry in api.day("2026-06-15")["entries"]] == ["Kolacja", "Kolacja Druga"]


def test_english_template_parser(api):
    response = api.client.post(
        "/api/chat/message",
        json={"user_id": api.uid, "message": "Date: 2026-06-14\nBreakfast\nCalories: 540\nCarbs: 48\nFat: 18\nProtein: 32"},
        headers=EN,
    )
    body = response.json()
    assert body["kind"] == "saved" and body["log_date"] == "2026-06-14"
    assert "Saved entry (14/06/2026): Breakfast – 540 kcal" in body["reply"]


def test_csv_in_english(api):
    api.chat("Waga: 82,4")
    lines = api.client.get(f"/api/export?user_id={api.uid}", headers=EN).text.lstrip("﻿").splitlines()
    assert lines[0] == "Date,Weight (kg),Waist (cm),Calories (kcal),Protein (g),Carbs (g),Fat (g)"
    assert lines[1] == "2026-06-15,82.4,,,,,"
    template = api.client.get(f"/api/import/template?user_id={api.uid}", headers=EN).text.lstrip("﻿").splitlines()
    assert template[0] == lines[0]
    # import angielskiego pliku z kropka dziesietna
    content = "Date,Weight (kg),Calories (kcal)\n2026-06-01,91.5,2000\n"
    result = api.client.post(f"/api/import?user_id={api.uid}", json={"content": content}, headers=EN).json()
    assert result["imported_days"] == 1


def test_plan_message_in_english(api):
    status = api.client.get(f"/api/profile/{api.uid}/plan", headers=EN).json()
    assert status["message"].startswith("No weight measurements")


def test_user_language_is_remembered(api, client):
    assert client.put(f"/api/users/{api.uid}/language", json={"language": "en"}, headers=PIN).status_code == 200
    session = client.post("/api/auth/verify", json={"user_id": api.uid, "pin": "1234"}).json()
    assert session["language"] == "en"
    assert client.put(f"/api/users/{api.uid}/language", json={"language": "de"}, headers=PIN).status_code == 422
