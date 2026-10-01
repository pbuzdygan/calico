"""T3.4 / SEC-04: ALLOW_SIGNUP wylacza zakladanie kont, ale pierwszy uzytkownik zawsze moze powstac (D10)."""

import pytest

from app.config import settings


@pytest.fixture
def signup_disabled(monkeypatch):
    monkeypatch.setattr(settings, "allow_signup", False)


def test_signup_enabled_by_default(client, uid):
    assert client.get("/api/meta").json()["allow_signup"] is True
    assert client.post("/api/users", json={"display_name": "Druga Osoba", "pin": "2468"}).status_code == 200


def test_first_user_allowed_when_signup_disabled(client, signup_disabled):
    assert client.get("/api/meta").json()["allow_signup"] is True  # brak uzytkownikow -> pierwszy start
    assert client.post("/api/users", json={"display_name": "Pierwsza", "pin": "2468"}).status_code == 200
    assert client.get("/api/meta").json()["allow_signup"] is False


def test_next_users_blocked_when_signup_disabled(client, uid, signup_disabled):
    response = client.post("/api/users", json={"display_name": "Intruz", "pin": "2468"})
    assert response.status_code == 403
    assert "wyłączone" in response.json()["detail"]
    assert [user["display_name"] for user in client.get("/api/users").json()] == ["Test"]
