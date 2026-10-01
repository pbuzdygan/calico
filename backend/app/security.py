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


def _sign(data: dict, secret: str) -> str:
    payload = _b64encode(json.dumps(data, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def _read_signed(token: str, secret: str, now: int, kind: str) -> dict | None:
    """Dane tokenu, jesli podpis jest poprawny, rodzaj sie zgadza i token nie wygasl; inaczej None."""
    try:
        payload, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_b64decode(payload))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict) or data.get("k", "s") != kind or int(data.get("exp", 0)) < now:
        return None
    return data


def create_session_token(user_id: int, pin_hash: str, secret: str, expires_at: int) -> str:
    return _sign({"uid": user_id, "exp": expires_at, "pv": pin_fingerprint(pin_hash)}, secret)


def read_session_token(token: str, secret: str, now: int) -> dict | None:
    return _read_signed(token, secret, now, "s")


# --- T-PUB: zaufane urzadzenie (po udanym logowaniu) - zwolnione z blokady konta przy atakach z innych adresow ---


def create_device_token(user_id: int, device_id: str, secret: str, expires_at: int) -> str:
    return _sign({"k": "d", "uid": user_id, "did": device_id, "exp": expires_at}, secret)


def read_device_token(token: str, secret: str, now: int) -> dict | None:
    return _read_signed(token, secret, now, "d")


def new_device_id() -> str:
    return secrets.token_hex(8)


def burn_pin_check(pin: str) -> None:
    """PBKDF2 dla nieistniejacego konta - czas odpowiedzi nie zdradza, czy uzytkownik istnieje."""
    hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), b"calico-no-such-user", 120_000)


# --- T-PUB: kod pierwszego uruchomienia (w logach kontenera) ------------------------------------------

SETUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # bez 0/O, 1/I


def new_setup_code() -> str:
    raw = "".join(secrets.choice(SETUP_CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalize_setup_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def setup_code_matches(given: str, expected: str) -> bool:
    return hmac.compare_digest(normalize_setup_code(given), normalize_setup_code(expected))


def is_trivial_pin(pin: str) -> bool:
    """Same powtorzenia (111111) albo kolejne cyfry rosnaco/malejaco (123456, 987654)."""
    if len(set(pin)) == 1:
        return True
    steps = {(int(b) - int(a)) for a, b in zip(pin, pin[1:], strict=False)}
    return steps in ({1}, {-1})


def new_secret() -> str:
    return secrets.token_hex(32)
