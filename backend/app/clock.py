from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from .config import settings


def now_utc() -> datetime:
    return datetime.now(UTC)


def utcnow_naive() -> datetime:
    """Znacznik czasu do bazy (naiwny UTC, jak dotychczasowe dane)."""
    return now_utc().replace(tzinfo=None)


def today() -> date:
    """Dzisiejsza data w strefie czasowej aplikacji (APP_TIMEZONE)."""
    return now_utc().astimezone(ZoneInfo(settings.app_timezone)).date()
