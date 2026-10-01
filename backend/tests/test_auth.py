from datetime import timedelta

from .conftest import PIN, complete_profile_directly


def login(client, user_id, pin="1234"):
    response = client.post("/api/auth/verify", json={"user_id": user_id, "pin": pin})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_verify_returns_session_token(api, client):
    session = login(client, api.uid)
    assert session["ok"] is True and session["token"] and session["expires_at"]
    response = client.get(f"/api/days/2026-06-15?user_id={api.uid}", headers=bearer(session["token"]))
    assert response.status_code == 200


def test_token_is_bound_to_user_and_signature(api, client):
    other = client.post("/api/users", json={"display_name": "Druga Osoba", "pin": "5555"}).json()
    complete_profile_directly(other["id"])
    token = login(client, api.uid)["token"]
    # token uzytkownika A nie otwiera danych uzytkownika B
    assert client.get(f"/api/days?user_id={other['id']}", headers=bearer(token)).status_code == 401
    payload, signature = token.split(".")
    forged = payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(forged)).status_code == 401
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer("smieci")).status_code == 401


def test_token_expires_after_ttl(api, client, frozen_clock):
    token = login(client, api.uid)["token"]
    frozen_clock["now"] += timedelta(hours=11, minutes=59)
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(token)).status_code == 200
    frozen_clock["now"] += timedelta(minutes=2)
    response = client.get(f"/api/days?user_id={api.uid}", headers=bearer(token))
    assert response.status_code == 401 and "Sesja wygasła" in response.json()["detail"]


def test_pin_change_invalidates_old_tokens_and_returns_new_one(api, client):
    old = login(client, api.uid)["token"]
    response = client.post(f"/api/users/{api.uid}/pin", json={"new_pin": "8642"}, headers=bearer(old))
    assert response.status_code == 200
    new = response.json()["token"]
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(old)).status_code == 401
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(new)).status_code == 200


def test_chat_and_profile_accept_token(api, client):
    token = login(client, api.uid)["token"]
    reply = client.post("/api/chat/message", json={"user_id": api.uid, "message": "pomoc"}, headers=bearer(token))
    assert reply.status_code == 200 and reply.json()["kind"] == "info"
    assert client.get(f"/api/profile/{api.uid}", headers=bearer(token)).json()["is_complete"] is True


def test_missing_credentials_rejected(api, client):
    assert client.get(f"/api/days?user_id={api.uid}").status_code == 401
    assert client.get(f"/api/days?user_id={api.uid}", headers=PIN).status_code == 200  # PIN w naglowku nadal dziala


# --- T3.1 / SEC-01: blokada po blednych PIN-ach ---------------------------------------------------


def verify(client, user_id, pin):
    return client.post("/api/auth/verify", json={"user_id": user_id, "pin": pin})


def test_wrong_pin_reports_remaining_attempts(api, client):
    response = verify(client, api.uid, "0000")
    assert response.status_code == 401
    assert "Pozostałe próby: 4" in response.json()["detail"]


def test_lockout_after_five_failures(api, client, frozen_clock):
    for _ in range(4):
        assert verify(client, api.uid, "0000").status_code == 401
    fifth = verify(client, api.uid, "0000")
    assert fifth.status_code == 401 and "Spróbuj ponownie za 5 min" in fifth.json()["detail"]
    # 6. proba - nawet z poprawnym PIN-em - jest blokowana
    response = verify(client, api.uid, "1234")
    assert response.status_code == 429
    assert "Spróbuj ponownie za 5 min" in response.json()["detail"]
    assert response.headers["Retry-After"] == "300"
    # X-User-PIN tez jest blokowany
    assert client.get(f"/api/days?user_id={api.uid}", headers=PIN).status_code == 429
    frozen_clock["now"] += timedelta(minutes=5, seconds=1)
    assert verify(client, api.uid, "1234").status_code == 200


def test_success_resets_failure_counter(api, client):
    for _ in range(4):
        verify(client, api.uid, "0000")
    assert verify(client, api.uid, "1234").status_code == 200
    for _ in range(4):
        assert verify(client, api.uid, "0000").status_code == 401
    assert verify(client, api.uid, "1234").status_code == 200


def test_lockout_doubles_up_to_limit(api, client, frozen_clock):
    expected_minutes = [5, 10, 20, 40, 60, 60]
    for minutes in expected_minutes:
        for _ in range(5):
            verify(client, api.uid, "0000")
        response = verify(client, api.uid, "1234")
        assert response.status_code == 429
        assert response.headers["Retry-After"] == str(minutes * 60)
        frozen_clock["now"] += timedelta(minutes=minutes, seconds=1)


def test_lockout_is_per_user(api, client):
    other = client.post("/api/users", json={"display_name": "Druga Osoba", "pin": "5555"}).json()
    for _ in range(6):
        verify(client, api.uid, "0000")
    assert verify(client, other["id"], "5555").status_code == 200


def test_session_token_works_during_lockout(api, client):
    """Blokada dotyczy zgadywania PIN-u; otwarta sesja dziala dalej."""
    token = login(client, api.uid)["token"]
    for _ in range(6):
        verify(client, api.uid, "0000")
    assert client.get(f"/api/days?user_id={api.uid}", headers=bearer(token)).status_code == 200
