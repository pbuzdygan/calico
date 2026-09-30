import json
from pathlib import Path

from sqlalchemy.orm import Session

from . import clock
from .config import settings
from .models import User


def diagnostics_enabled() -> bool:
    return bool(settings.admin_pin.strip())


def diagnostics_dir() -> Path:
    path = Path(settings.diagnostics_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_log_path(user: User) -> Path:
    safe_slug = user.slug or f"user-{user.id}"
    return diagnostics_dir() / f"user_{user.id}_{safe_slug}.jsonl"


def log_chat_interaction(
    user: User,
    user_message: str,
    response_payload: dict | None = None,
    error_text: str | None = None,
) -> None:
    if not diagnostics_enabled():
        return

    payload = {
        "timestamp": clock.now_utc().isoformat(timespec="seconds").replace("+00:00", "Z"),
        "user_id": user.id,
        "user_slug": user.slug,
        "display_name": user.display_name,
        "user_message": user_message,
        "outcome": "error" if error_text else "success",
    }
    if response_payload is not None:
        payload["response"] = response_payload
    if error_text:
        payload["error"] = error_text

    with user_log_path(user).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def delete_user_diagnostics(user: User) -> None:
    for path in diagnostics_dir().glob(f"user_{user.id}_*.jsonl"):
        if path.exists():
            path.unlink()


def diagnostics_user_summaries(db: Session) -> list[dict]:
    summaries: list[dict] = []
    users = db.query(User).order_by(User.display_name.asc()).all()
    for user in users:
        path = user_log_path(user)
        entries_count = 0
        last_event_at = None
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    entries_count += 1
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    last_event_at = payload.get("timestamp", last_event_at)
        summaries.append(
            {
                "user_id": user.id,
                "display_name": user.display_name,
                "slug": user.slug,
                "entries_count": entries_count,
                "last_event_at": last_event_at,
                "file_name": path.name,
            }
        )
    return summaries


def diagnostics_entries_for_user(user: User, limit: int = 200) -> list[dict]:
    path = user_log_path(user)
    if not path.exists():
        return []

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit > 0:
        rows = rows[-limit:]
    rows.reverse()
    return rows
