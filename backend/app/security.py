import hashlib
import hmac
import os
import re


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
