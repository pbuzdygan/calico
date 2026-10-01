"""Utwardzenie przed publicznym obrazem: dokumentacja API wylaczona, limit rozmiaru zadania, naglowki."""


def test_api_docs_disabled_by_default(client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_request_body_too_large_is_rejected(client):
    response = client.post(
        "/api/users",
        content=b"x" * 10,
        headers={"Content-Type": "application/json", "Content-Length": str(5 * 1024 * 1024)},
    )
    assert response.status_code == 413
    assert "za duże" in response.json()["detail"]


def test_request_body_too_large_in_english(client):
    response = client.post(
        "/api/users",
        content=b"x" * 10,
        headers={"Content-Type": "application/json", "Content-Length": str(5 * 1024 * 1024), "Accept-Language": "en"},
    )
    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def test_import_sized_body_is_accepted(client, uid):
    # Najwiekszy dopuszczalny import (1 000 000 znakow) miesci sie w limicie zadania.
    response = client.post(
        f"/api/import?user_id={uid}",
        json={"content": "#" + "x" * 999_000},
        headers={"X-User-PIN": "1234"},
    )
    assert response.status_code != 413


def test_security_headers(client):
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Permissions-Policy"].startswith("camera=()")
    assert headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    assert "server" not in {key.lower() for key in headers}
