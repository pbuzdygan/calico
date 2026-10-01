import base64
import hashlib
import hmac
import json
import os
import re
import secrets


PIN_PATTERN = re.compile(r"^\d{4,8}$")


def validate_pin(pin: str) -> bool:
    return bool(PIN_PATTERN.fullmatch(pin or ""))


def hash_pin(pin: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 120_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_pin(pin: str, pin_hash: str | None) -> bool:
    if not pin_hash or ":" not in pin_hash:
        return False
    try:
        salt_hex, digest_hex = pin_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(actual, expected)


# --- sesje: podpisany token (HMAC-SHA256) zamiast PIN-u w kazdym zapytaniu ---------------------------


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def pin_fingerprint(pin_hash: str) -> str:
    """Zmiana PIN-u zmienia odcisk, wiec uniewaznia wszystkie wczesniejsze tokeny."""
    return hashlib.sha256((pin_hash or "").encode("utf-8")).hexdigest()[:16]


def create_session_token(user_id: int, pin_hash: str, secret: str, expires_at: int) -> str:
    payload = _b64encode(json.dumps({"uid": user_id, "exp": expires_at, "pv": pin_fingerprint(pin_hash)}, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_session_token(token: str, secret: str, now: int) -> dict | None:
    """Zwraca dane tokenu, jesli podpis jest poprawny i token nie wygasl; inaczej None."""
    try:
        payload, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or int(data.get("exp", 0)) < now:
        return None
    return data


def new_secret() -> str:
    return secrets.token_hex(32)
