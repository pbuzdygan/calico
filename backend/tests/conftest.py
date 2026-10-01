import os
import tempfile
from datetime import UTC, datetime

_TMP_DIR = tempfile.mkdtemp(prefix="calico-tests-")
os.environ["SQLITE_PATH"] = os.path.join(_TMP_DIR, "test.db")
os.environ["APP_TIMEZONE"] = "Europe/Warsaw"
os.environ["FRONTEND_DIR"] = os.path.join(_TMP_DIR, "no-frontend")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import clock  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.login_guard import guard  # noqa: E402
from app.main import app  # noqa: E402

# 2026-06-15 12:00 czasu polskiego
FROZEN_NOW = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
TEST_PIN = "135790"
# Naglowek Authorization zalogowanego uzytkownika testowego (uzupelnia fixture uid). PIN dziala tylko w /api/auth/verify.
AUTH: dict[str, str] = {}


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    state = {"now": FROZEN_NOW}
    monkeypatch.setattr(clock, "now_utc", lambda: state["now"])
    return state


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def reset_login_guard():
    guard.reset()  # limity logowania w pamieci procesu - kazdy test od zera
    yield
    guard.reset()


def setup_code():
    """Kod pierwszego uruchomienia (T-PUB) - None, gdy konta juz istnieja."""
    from app import services
    from app.db import SessionLocal

    with SessionLocal() as db:
        code = services.ensure_setup_code(db)
        db.commit()
    return code


def create_user(client, display_name, pin=TEST_PIN):
    payload = {"display_name": display_name, "pin": pin}
    code = setup_code()
    if code:
        payload["setup_code"] = code
    response = client.post("/api/users", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def login(client, user_id, pin=TEST_PIN, **extra):
    response = client.post("/api/auth/verify", json={"user_id": user_id, "pin": pin, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def auth_for(client, user_id, pin=TEST_PIN):
    return bearer(login(client, user_id, pin)["token"])


@pytest.fixture
def uid(client):
    # D10: brak uzytkownika domyslnego - pierwszy uzytkownik zakladany jawnie (z kodem pierwszego uruchomienia)
    from app.config import settings

    user = create_user(client, "Test")
    ttl = settings.session_ttl_hours
    settings.session_ttl_hours = 24 * 3650  # testy przesuwaja zegar o dni - sesja testowa nie wygasa
    try:
        AUTH.clear()
        AUTH.update(auth_for(client, user["id"]))
    finally:
        settings.session_ttl_hours = ttl
    return user["id"]


class Api:
    def __init__(self, client, uid):
        self.client = client
        self.uid = uid

    def chat(self, message):
        response = self.client.post("/api/chat/message", json={"user_id": self.uid, "message": message}, headers=AUTH)
        assert response.status_code == 200, response.text
        return response.json()

    def get(self, path, **params):
        params.setdefault("user_id", self.uid)
        return self.client.get(path, params=params, headers=AUTH)

    def post(self, path, json=None, **params):
        params.setdefault("user_id", self.uid)
        return self.client.post(path, params=params, json=json, headers=AUTH)

    def patch(self, path, json=None, **params):
        params.setdefault("user_id", self.uid)
        return self.client.patch(path, params=params, json=json, headers=AUTH)

    def delete(self, path, **params):
        params.setdefault("user_id", self.uid)
        return self.client.delete(path, params=params, headers=AUTH)

    def day(self, log_date):
        response = self.get(f"/api/days/{log_date}")
        assert response.status_code == 200, response.text
        return response.json()

    def profile(self):
        return self.client.get(f"/api/profile/{self.uid}", headers=AUTH).json()

    def put_profile(self, **overrides):
        payload = {
            "sex": "male",
            "age": 30,
            "height_cm": 180,
            "weight_kg": 90,
            "activity_level": "moderate",
            "goal_type": "maintain",
            "goal_delta_pct": 0.0,
        }
        payload.update(overrides)
        response = self.client.put(f"/api/profile/{self.uid}", json=payload, headers=AUTH)
        assert response.status_code == 200, response.text
        return response.json()


def complete_profile_directly(user_id, weight_kg=90.0):
    """Kompletny profil bez tworzenia wpisu 'Waga' (zeby nie zaburzac testow dni)."""
    from app import clock, services
    from app.db import SessionLocal
    from app.models import Profile

    with SessionLocal() as db:
        profile = Profile(
            user_id=user_id,
            sex="male",
            age=30,
            height_cm=180,
            weight_kg=weight_kg,
            activity_level="moderate",
            goal_type="maintain",
            goal_delta_pct=0.0,
            completed_at=clock.utcnow_naive(),
        )
        db.add(profile)
        db.flush()
        services.set_plan_target(db, profile, services.calculate_target(profile), services.calculate_tdee(profile))
        db.commit()


@pytest.fixture
def api(client, uid):
    complete_profile_directly(uid)
    return Api(client, uid)


@pytest.fixture
def fresh_api(client, uid):
    """Uzytkownik bez uzupelnionego profilu (jak po instalacji)."""
    return Api(client, uid)


def meal(header="Obiad", kcal=500, carbs=50, fat=20, protein=30, date_line=None):
    lines = [f"Data: {date_line}"] if date_line else []
    lines += [header, f"Ilość kalorii: {kcal}", f"Węglowodany: {carbs}", f"Tłuszcze: {fat}", f"Białko: {protein}"]
    return "\n".join(lines)
