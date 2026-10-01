"""Tlumaczenia komunikatow API (PL - jezyk zrodlowy, EN - slownik app/locales/en.py).

Zasada: kazdy tekst dla uzytkownika przechodzi przez t("Polski tekst z {parametrami}", parametr=...).
Klucz to polski tekst; angielski odpowiednik musi byc w locales/en.py - pilnuje tego tests/test_i18n.py
(brakujace i nieuzywane tlumaczenia, polskie znaki poza t()).

Jezyk zadania: naglowek Accept-Language (frontend wysyla wybrany jezyk), ustawiany w middleware.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from .locales.en import MESSAGES as EN_MESSAGES

LANGUAGES = ("pl", "en")
DEFAULT_LANGUAGE = "pl"
LOCALES = {"pl": "pl-PL", "en": "en-GB"}

_current_language: ContextVar[str] = ContextVar("calico_language", default=DEFAULT_LANGUAGE)


def get_language() -> str:
    return _current_language.get()


def set_language(language: str) -> None:
    _current_language.set(language if language in LANGUAGES else DEFAULT_LANGUAGE)


@contextmanager
def use_language(language: str) -> Iterator[None]:
    """Np. kanoniczne (polskie) teksty zapisywane w bazie niezaleznie od jezyka zadania."""
    token = _current_language.set(language)
    try:
        yield
    finally:
        _current_language.reset(token)


def language_from_header(header: str | None) -> str:
    """Pierwszy obslugiwany jezyk z Accept-Language (np. 'en-GB,en;q=0.9' -> 'en')."""
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower().split("-")[0]
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def t(text: str, **params: object) -> str:
    """Tlumaczenie polskiego tekstu na jezyk zadania; parametry w formacie {nazwa}."""
    template = text if get_language() == "pl" else EN_MESSAGES.get(text, text)
    return template.format(**params) if params else template
