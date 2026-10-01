"""Sesje i logowanie (T3.2, T-PUB): token zamiast PIN-u, limity per IP / para konto+zrodlo / konto,
zaufane urzadzenia, polityka PIN-u, wymuszona zmiana krotkiego PIN-u, ukryta lista uzytkownikow, kod pierwszego uruchomienia."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

from .conftest import AUTH, TEST_PIN, bearer, complete_profile_directly, create_user, login, setup_code

WRONG = "000111"


def from_ip(ip):
    """Klient z innym adresem IP (bez lifespan - baza jest juz przygotowana przez fixture client)."""
    return TestClient(app, client=(ip, 50000))


def verify(client, pin, user_id=None, **extra):
    payload = {"pin": pin, **extra}
    if user_id is not None:
        payload["user_id"] = user_id
    return client.post("/api/auth/verify", json=payload)


# --- sesja ---------------------------------------------------------------------------------------------


def test_verify_returns_session_token(api, client):
    session = login(client, api.uid)
    assert session["ok"] is True and session["token"] and session["expires_at"] and session["device_token"]
    assert session["user_id"] == api.uid and session["display_name"] == "Test" and session["pin_change_required"] is False
    response = client.get(f"/api/days/2026-06-15?user_id={api.uid}", headers=bearer(session["token"]))
    assert response.status_code == 200


def test_token_is_bound_to_user_and_signature(api, client):
    other = create_user(client, "Druga Osoba")
    complete_profile_directly(other["id"])
    token = login(client, api.uid)["token"]
    # token uzytkownika A nie otwiera danych uzytkownika B
    assert client.get(f"/api/days?user_id={other['id']}", headers=bearer(token)).status_code == 401
    payload, signature = token.split(".")
    forged = payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(forged)).status_code == 401
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer("smieci")).status_code == 401


def test_device_token_is_not_a_session(api, client):
    device_token = login(client, api.uid)["device_token"]
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(device_token)).status_code == 401


def test_token_expires_after_ttl(api, client, frozen_clock):
    token = login(client, api.uid)["token"]
    frozen_clock["now"] += timedelta(hours=11, minutes=59)
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(token)).status_code == 200
    frozen_clock["now"] += timedelta(minutes=2)
    response = client.get(f"/api/days?user_id={api.uid}", headers=bearer(token))
    assert response.status_code == 401 and "Sesja wygasła" in response.json()["detail"]


def test_chat_and_profile_accept_token(api, client):
    token = login(client, api.uid)["token"]
    reply = client.post("/api/chat/message", json={"user_id": api.uid, "message": "pomoc"}, headers=bearer(token))
    assert reply.status_code == 200 and reply.json()["kind"] == "info"
    assert client.get(f"/api/profile/{api.uid}", headers=bearer(token)).json()["is_complete"] is True


def test_pin_header_no_longer_accepted(api, client):
    """T-PUB: PIN tylko w POST /api/auth/verify - pozostale endpointy nie sa wyrocznia do zgadywania."""
    assert client.get(f"/api/days?user_id={api.uid}").status_code == 401
    assert client.get(f"/api/days?user_id={api.uid}", headers={"X-User-PIN": TEST_PIN}).status_code == 401
    message = {"user_id": api.uid, "message": "pomoc"}
    assert client.post("/api/chat/message", json=message, headers={"X-User-PIN": TEST_PIN}).status_code == 401


# --- para konto + zrodlo -------------------------------------------------------------------------------


def test_wrong_pin_reports_remaining_attempts(api, client):
    response = verify(client, WRONG, api.uid)
    assert response.status_code == 401
    assert response.json()["detail"] == "Niepoprawny PIN. Pozostałe próby: 4."


def test_lockout_after_five_failures(api, client, frozen_clock):
    for _ in range(4):
        assert verify(client, WRONG, api.uid).status_code == 401
    fifth = verify(client, WRONG, api.uid)
    assert fifth.status_code == 401 and "Spróbuj ponownie za 5 min" in fifth.json()["detail"]
    # 6. proba - nawet z poprawnym PIN-em - jest blokowana
    response = verify(client, TEST_PIN, api.uid)
    assert response.status_code == 429
    assert "Spróbuj ponownie za 5 min" in response.json()["detail"]
    assert 299 <= int(response.headers["Retry-After"]) <= 301
    frozen_clock["now"] += timedelta(minutes=5, seconds=2)
    assert verify(client, TEST_PIN, api.uid).status_code == 200


def test_success_resets_failure_counter(api, client):
    for _ in range(4):
        verify(client, WRONG, api.uid)
    assert verify(client, TEST_PIN, api.uid).status_code == 200
    for _ in range(4):
        assert verify(client, WRONG, api.uid).status_code == 401
    assert verify(client, TEST_PIN, api.uid).status_code == 200


def test_pair_lockout_doubles_up_to_limit(api, frozen_clock):
    """Kazda seria z innego IP (zeby nie wpasc w limit IP) - eskalacja liczona per para, tu: jedno IP i jedno konto."""
    attacker = from_ip("203.0.113.7")
    for minutes in [5, 10, 20, 40, 60, 60]:
        for _ in range(5):
            verify(attacker, WRONG, api.uid)
        response = verify(attacker, TEST_PIN, api.uid)
        assert response.status_code == 429
        assert abs(int(response.headers["Retry-After"]) - minutes * 60) <= 1, minutes
        frozen_clock["now"] += timedelta(minutes=minutes, seconds=2)
        if minutes == 60:
            break
        # okno limitu IP (15 min) mija przy dluzszych blokadach; przy 5 i 10 min nie - wtedy czekamy dodatkowo
        if minutes < 15:
            frozen_clock["now"] += timedelta(minutes=15)


def test_attacker_cannot_lock_out_owner(api, client):
    """Bledne PIN-y z obcego adresu blokuja tylko atakujacego, wlasciciel loguje sie dalej."""
    attacker = from_ip("198.51.100.23")
    for _ in range(6):
        verify(attacker, WRONG, api.uid)
    assert verify(attacker, TEST_PIN, api.uid).status_code == 429
    assert verify(client, TEST_PIN, api.uid).status_code == 200


def test_session_token_works_during_lockout(api, client):
    """Blokada dotyczy zgadywania PIN-u; otwarta sesja dziala dalej."""
    token = login(client, api.uid)["token"]
    for _ in range(6):
        verify(client, WRONG, api.uid)
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(token)).status_code == 200


# --- limit per IP --------------------------------------------------------------------------------------


def test_ip_blocked_after_ten_failures_across_accounts(api, client, frozen_clock):
    other = create_user(client, "Druga Osoba")
    attacker = from_ip("192.0.2.50")
    for user_id in (api.uid, other["id"]):
        for _ in range(4):
            assert verify(attacker, WRONG, user_id).status_code == 401
    for _ in range(2):
        verify(attacker, WRONG, 999)  # nieistniejace konto liczy sie tak samo
    response = verify(attacker, TEST_PIN, other["id"])
    assert response.status_code == 429 and "z tego adresu" in response.json()["detail"]
    assert verify(client, TEST_PIN, api.uid).status_code == 200  # inne adresy bez zmian
    frozen_clock["now"] += timedelta(minutes=15, seconds=2)
    assert verify(attacker, TEST_PIN, other["id"]).status_code == 200


def test_trusted_device_not_blocked_by_ip_limit(api, client):
    device_token = login(client, api.uid)["device_token"]
    for name in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"):
        verify(client, WRONG, name=name)
    assert verify(client, TEST_PIN, api.uid).status_code == 429
    assert verify(client, TEST_PIN, api.uid, device_tokens=[device_token]).status_code == 200


# --- blokada konta (ataki z wielu adresow) i zaufane urzadzenia -----------------------------------------


def _distributed_attack(user_id, failures):
    for index in range(failures):
        verify(from_ip(f"10.0.{index // 4}.1"), WRONG, user_id)  # po 4 proby z adresu - ponizej limitu pary


def test_account_lock_after_distributed_attack(api, client):
    device_token = login(client, api.uid)["device_token"]
    _distributed_attack(api.uid, 20)
    newcomer = verify(from_ip("10.9.9.9"), TEST_PIN, api.uid)
    assert newcomer.status_code == 429  # nowe urzadzenie czeka (15 min)
    assert 899 <= int(newcomer.headers["Retry-After"]) <= 901
    trusted = verify(client, TEST_PIN, api.uid, device_tokens=[device_token])
    assert trusted.status_code == 200  # wlasciciel na swoim urzadzeniu loguje sie mimo ataku
    assert trusted.json()["failed_attempts"] == 20  # i widzi, ze ktos probowal


def test_owner_sign_in_does_not_reset_account_escalation(api, client, frozen_clock):
    """Codzienne logowanie wlasciciela nie odnawia puli prob atakujacego."""
    device_token = login(client, api.uid)["device_token"]
    _distributed_attack(api.uid, 20)
    assert verify(client, TEST_PIN, api.uid, device_tokens=[device_token]).status_code == 200
    frozen_clock["now"] += timedelta(minutes=16)
    for index in range(4):
        verify(from_ip(f"10.1.{index}.1"), WRONG, api.uid)
    fifth = verify(from_ip("10.1.9.1"), WRONG, api.uid)  # 25. blad - kolejna blokada (30 min), mimo udanego logowania
    assert "30 min" in fifth.json()["detail"]
    assert verify(from_ip("10.2.0.1"), TEST_PIN, api.uid).status_code == 429


def test_account_escalation_forgotten_after_quiet_week(api, client, frozen_clock):
    _distributed_attack(api.uid, 20)
    frozen_clock["now"] += timedelta(days=7, minutes=1)
    for index in range(4):
        assert verify(from_ip(f"10.3.{index}.1"), WRONG, api.uid).status_code == 401
    assert verify(from_ip("10.4.0.1"), TEST_PIN, api.uid).status_code == 200


def test_failed_attempts_reset_after_success(api, client):
    verify(client, WRONG, api.uid)
    assert login(client, api.uid)["failed_attempts"] == 1
    assert login(client, api.uid)["failed_attempts"] == 0


def test_device_token_of_other_user_is_ignored(api, client):
    other = create_user(client, "Druga Osoba")
    foreign_token = login(client, other["id"])["device_token"]
    _distributed_attack(api.uid, 20)
    assert verify(from_ip("10.9.9.9"), TEST_PIN, api.uid, device_tokens=[foreign_token, "smieci"]).status_code == 429


def test_trusted_device_still_limited_per_device(api, client):
    """Skradzione urzadzenie z tokenem nie ma nieograniczonej liczby prob."""
    device_token = login(client, api.uid)["device_token"]
    for _ in range(5):
        verify(client, WRONG, api.uid, device_tokens=[device_token])
    assert verify(client, TEST_PIN, api.uid, device_tokens=[device_token]).status_code == 429


# --- polityka PIN-u ------------------------------------------------------------------------------------


@pytest.mark.parametrize("pin", ["1234", "12345", "123456", "654321", "111111", "00000000"])
def test_weak_new_pin_rejected(client, uid, pin):
    response = client.post("/api/users", json={"display_name": "Nowy", "pin": pin})
    assert response.status_code == 422


def test_pin_min_length_is_configurable(client, uid, monkeypatch):
    monkeypatch.setattr(settings, "pin_min_length", 8)
    response = client.post("/api/users", json={"display_name": "Nowy", "pin": "1357902"})
    assert response.status_code == 422 and "8–8 cyfr" in response.json()["detail"]
    assert client.get("/api/meta").json()["pin_min_length"] == 8


def test_pin_change_requires_current_pin(api, client):
    url = f"/api/users/{api.uid}/pin"
    wrong = client.post(url, json={"current_pin": WRONG, "new_pin": "864209"}, headers=AUTH)
    assert wrong.status_code == 403 and "Pozostałe próby: 4" in wrong.json()["detail"]
    same = client.post(url, json={"current_pin": TEST_PIN, "new_pin": TEST_PIN}, headers=AUTH)
    assert same.status_code == 422
    weak = client.post(url, json={"current_pin": TEST_PIN, "new_pin": "222222"}, headers=AUTH)
    assert weak.status_code == 422
    old_token = AUTH["Authorization"]
    ok = client.post(url, json={"current_pin": TEST_PIN, "new_pin": "864209"}, headers=AUTH)
    assert ok.status_code == 200
    assert client.get(f"/api/days?user_id={api.uid}", headers={"Authorization": old_token}).status_code == 401
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(ok.json()["token"])).status_code == 200


def test_pin_change_locked_after_wrong_current_pins(api, client):
    url = f"/api/users/{api.uid}/pin"
    for _ in range(5):
        client.post(url, json={"current_pin": WRONG, "new_pin": "864209"}, headers=AUTH)
    assert client.post(url, json={"current_pin": TEST_PIN, "new_pin": "864209"}, headers=AUTH).status_code == 429


# --- wymuszona zmiana krotkiego PIN-u ------------------------------------------------------------------


def _set_pin_directly(user_id, pin):
    from app.db import SessionLocal
    from app.models import User
    from app.security import hash_pin

    with SessionLocal() as db:
        db.get(User, user_id).pin_hash = hash_pin(pin)
        db.commit()


def test_short_pin_forces_change_before_anything_else(api, client):
    _set_pin_directly(api.uid, "4826")  # konto sprzed T-PUB
    session = login(client, api.uid, "4826")
    assert session["pin_change_required"] is True
    headers = bearer(session["token"])
    for response in (
        client.get(f"/api/days?user_id={api.uid}", headers=headers),
        client.get(f"/api/profile/{api.uid}", headers=headers),
        client.post("/api/chat/message", json={"user_id": api.uid, "message": "pomoc"}, headers=headers),
    ):
        assert response.status_code == 428 and response.json()["code"] == "pin_change_required"
    assert client.put(f"/api/users/{api.uid}/language", json={"language": "en"}, headers=headers).status_code == 200
    changed = client.post(f"/api/users/{api.uid}/pin", json={"current_pin": "4826", "new_pin": "730518"}, headers=headers)
    assert changed.status_code == 200
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(changed.json()["token"])).status_code == 200
    assert login(client, api.uid, "730518")["pin_change_required"] is False


def test_short_pin_allowed_when_min_length_lowered(api, client, monkeypatch):
    monkeypatch.setattr(settings, "pin_min_length", 4)
    _set_pin_directly(api.uid, "4826")
    assert login(client, api.uid, "4826")["pin_change_required"] is False


def test_profile_required_has_code(fresh_api, client):
    response = fresh_api.get("/api/days")
    assert response.status_code == 428 and response.json()["code"] == "profile_required"


# --- ukryta lista uzytkownikow -------------------------------------------------------------------------


@pytest.fixture
def hidden_list(monkeypatch):
    monkeypatch.setattr(settings, "show_user_list", False)


def test_hidden_user_list(api, client, hidden_list):
    assert client.get("/api/meta").json()["show_user_list"] is False
    assert client.get("/api/users").status_code == 403
    session = verify(client, TEST_PIN, name="  test ")
    assert session.status_code == 200 and session.json()["user_id"] == api.uid


def test_unknown_name_looks_like_wrong_pin(api, client, hidden_list):
    unknown = verify(client, TEST_PIN, name="Nikt")
    wrong = verify(client, WRONG, name="Test")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"] == "Niepoprawna nazwa lub PIN. Pozostałe próby: 4."


def test_login_requires_user_or_name(client, uid):
    assert client.post("/api/auth/verify", json={"pin": TEST_PIN}).status_code == 422


# --- kod pierwszego uruchomienia -----------------------------------------------------------------------


def test_first_user_requires_setup_code(client):
    assert client.get("/api/meta").json()["setup_required"] is True
    payload = {"display_name": "Pierwsza", "pin": TEST_PIN}
    missing = client.post("/api/users", json=payload)
    assert missing.status_code == 403 and "kod pierwszego uruchomienia" in missing.json()["detail"]
    assert client.post("/api/users", json={**payload, "setup_code": "AAAA-BBBB-CCCC"}).status_code == 403
    code = setup_code()
    assert code == setup_code()  # stabilny do czasu utworzenia konta (te same logi po restarcie)
    created = client.post("/api/users", json={**payload, "setup_code": code.lower().replace("-", " ")})
    assert created.status_code == 200
    assert client.get("/api/meta").json()["setup_required"] is False
    assert setup_code() is None  # kod przestaje istniec
    # kolejne konta bez kodu (ALLOW_SIGNUP=true)
    assert client.post("/api/users", json={"display_name": "Druga", "pin": "864209"}).status_code == 200


def test_setup_code_guessing_blocks_ip(client):
    for _ in range(10):
        client.post("/api/users", json={"display_name": "Intruz", "pin": TEST_PIN, "setup_code": "ZZZZ-ZZZZ-ZZZZ"})
    response = client.post("/api/users", json={"display_name": "Intruz", "pin": TEST_PIN, "setup_code": setup_code()})
    assert response.status_code == 429


def test_setup_code_is_logged_on_first_start(caplog):
    from app import main

    with caplog.at_level("WARNING", logger="uvicorn.error"):
        main._announce_setup_code()
    assert setup_code() in caplog.text
