import re
from datetime import date, datetime

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal, healthcheck, init_db
from .diagnostics import diagnostics_enabled, diagnostics_entries_for_user, diagnostics_user_summaries, log_chat_interaction
from .models import DayEntry, Profile, User
from .schemas import (
    AdminStatusOut,
    AdminVerifyIn,
    AuthVerifyIn,
    AuthVerifyOut,
    ChatMessageIn,
    ChatResponseOut,
    DayDetailOut,
    DayEntryMoveIn,
    DayEntryOut,
    DayEntryUpdateIn,
    DaySummaryOut,
    DiagnosticsLogEntryOut,
    DiagnosticsUserSummaryOut,
    ProfileIn,
    ProfileOut,
    ReportSummaryOut,
    UserCreate,
    UserOut,
)
from .services import (
    COMMAND_SHOW_TODAY,
    COMMAND_SUMMARY,
    COMMAND_UNDO,
    clear_day_entries,
    close_day,
    create_day_entry,
    create_user,
    day_entry_by_id,
    day_entry_by_position,
    day_summary,
    delete_day_entry_by_id,
    delete_day_entry_by_position,
    delete_user,
    format_day_overview,
    format_entry_summary,
    get_day_log,
    get_or_create_day_log,
    help_text,
    list_day_entries,
    list_day_logs,
    list_users,
    parse_month_to_range,
    parse_template_message,
    recalculate_day_totals,
    report_for_range,
    reopen_day,
    require_user_pin,
    undo_last_entry,
    update_day_entry_from_payload,
    upsert_profile,
)

app = FastAPI(title=settings.app_name)
DELETE_POSITION_PATTERN = re.compile(r"\busun(?:\s+pozycje)?(?:\s+nr)?\s+(\d+)\b", flags=re.IGNORECASE)


def build_day_detail(day_log, entries) -> DayDetailOut:
    entry_items = [
        DayEntryOut(
            id=entry.id,
            position=index,
            entry_type=entry.entry_type,
            entry_label=entry.entry_label,
            source_text=entry.source_text,
            kcal=round(entry.kcal, 1) if entry.kcal is not None else None,
            carbs_g=round(entry.carbs_g, 1) if entry.carbs_g is not None else None,
            fat_g=round(entry.fat_g, 1) if entry.fat_g is not None else None,
            protein_g=round(entry.protein_g, 1) if entry.protein_g is not None else None,
            weight_kg=round(entry.weight_kg, 2) if entry.weight_kg is not None else None,
            waist_cm=round(entry.waist_cm, 1) if entry.waist_cm is not None else None,
            created_at=entry.created_at,
        )
        for index, entry in enumerate(entries, start=1)
    ]
    return DayDetailOut(
        user_id=day_log.user_id,
        log_date=day_log.log_date,
        status=day_log.status,
        total_kcal=round(day_log.total_kcal, 1),
        target_kcal=round(day_log.daily_kcal_target_snapshot, 1),
        total_carbs_g=round(day_log.total_carbs_g, 1),
        total_fat_g=round(day_log.total_fat_g, 1),
        total_protein_g=round(day_log.total_protein_g, 1),
        balance_mode=bool(day_log.balance_mode),
        entries=entry_items,
    )


def require_admin_pin(pin: str) -> None:
    if not diagnostics_enabled():
        raise HTTPException(status_code=404, detail="Admin mode disabled")
    if pin != settings.admin_pin:
        raise HTTPException(status_code=401, detail="Invalid admin PIN")


def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.on_event("startup")
def startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin] if settings.cors_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"ok": healthcheck()}


@app.get("/api/admin/status", response_model=AdminStatusOut)
def api_admin_status():
    return AdminStatusOut(enabled=diagnostics_enabled())


@app.post("/api/admin/verify", response_model=AuthVerifyOut)
def api_admin_verify(payload: AdminVerifyIn):
    require_admin_pin(payload.pin)
    return AuthVerifyOut(ok=True)


@app.get("/api/admin/diagnostics/users", response_model=list[DiagnosticsUserSummaryOut])
def api_admin_diagnostics_users(
    db: Session = Depends(get_db),
    x_admin_pin: str = Header(..., alias="X-Admin-PIN"),
):
    require_admin_pin(x_admin_pin)
    return diagnostics_user_summaries(db)


@app.get("/api/admin/diagnostics/logs", response_model=list[DiagnosticsLogEntryOut])
def api_admin_diagnostics_logs(
    user_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
    x_admin_pin: str = Header(..., alias="X-Admin-PIN"),
):
    require_admin_pin(x_admin_pin)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    safe_limit = min(max(limit, 1), 1000)
    return diagnostics_entries_for_user(user, limit=safe_limit)


@app.get("/api/users", response_model=list[UserOut])
def api_list_users(db: Session = Depends(get_db)):
    return list_users(db)


@app.post("/api/users", response_model=UserOut)
def api_create_user(payload: UserCreate, db: Session = Depends(get_db)):
    try:
        return create_user(db, payload.display_name, payload.pin)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.delete("/api/users/{user_id}", response_model=AuthVerifyOut)
def api_delete_user(user_id: int, db: Session = Depends(get_db), x_user_pin: str = Header(..., alias="X-User-PIN")):
    user = require_user_pin(db, user_id, x_user_pin)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    delete_user(db, user)
    return AuthVerifyOut(ok=True)


@app.post("/api/auth/verify", response_model=AuthVerifyOut)
def api_verify_auth(payload: AuthVerifyIn, db: Session = Depends(get_db)):
    user = require_user_pin(db, payload.user_id, payload.pin)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return AuthVerifyOut(ok=True)


@app.get("/api/profile/{user_id}", response_model=ProfileOut)
def api_get_profile(user_id: int, db: Session = Depends(get_db), x_user_pin: str = Header(..., alias="X-User-PIN")):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.put("/api/profile/{user_id}", response_model=ProfileOut)
def api_put_profile(user_id: int, payload: ProfileIn, db: Session = Depends(get_db), x_user_pin: str = Header(..., alias="X-User-PIN")):
    user = require_user_pin(db, user_id, x_user_pin)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return upsert_profile(db, user_id=user_id, payload=payload)


@app.get("/api/days/current", response_model=DaySummaryOut)
def api_current_day(user_id: int, db: Session = Depends(get_db), x_user_pin: str = Header(..., alias="X-User-PIN")):
    user = require_user_pin(db, user_id, x_user_pin)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=date.today())
    recalculate_day_totals(db, day_log)
    return day_summary(day_log)


@app.get("/api/days", response_model=list[DaySummaryOut])
def api_list_days(
    user_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    days = list_day_logs(db, user_id=user_id, limit=limit)
    return [day_summary(day) for day in days]


@app.get("/api/days/{log_date}", response_model=DayDetailOut)
def api_day_detail(
    log_date: date,
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=log_date)
    recalculate_day_totals(db, day_log)
    entries = list_day_entries(db, day_log)
    return build_day_detail(day_log, entries)


@app.post("/api/days/{log_date}/close", response_model=DaySummaryOut)
def api_close_day_by_date(
    log_date: date,
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=log_date)
    close_day(db, day_log)
    return day_summary(day_log)


@app.post("/api/days/{log_date}/reopen", response_model=DaySummaryOut)
def api_reopen_day(
    log_date: date,
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=log_date)
    reopen_day(db, day_log)
    return day_summary(day_log)


@app.post("/api/days/{log_date}/clear", response_model=DayDetailOut)
def api_clear_day(
    log_date: date,
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=log_date)
    clear_day_entries(db, day_log)
    entries = list_day_entries(db, day_log)
    return build_day_detail(day_log, entries)


@app.patch("/api/days/{log_date}/entries/{entry_id}", response_model=DayDetailOut)
def api_edit_day_entry(
    log_date: date,
    entry_id: int,
    payload: DayEntryUpdateIn,
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=log_date)
    entry = day_entry_by_id(db, day_log, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    try:
        parsed = parse_template_message(payload.source_text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    parsed.log_date = log_date
    updated_entry, target_day, _old_day = update_day_entry_from_payload(
        db,
        entry=entry,
        user_id=user_id,
        payload=parsed,
        fallback_date=log_date,
    )
    entries = list_day_entries(db, target_day)
    return build_day_detail(updated_entry.day_log, entries)


@app.delete("/api/days/{log_date}/entries/{entry_id}", response_model=DayDetailOut)
def api_delete_day_entry(
    log_date: date,
    entry_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    day_log = get_or_create_day_log(db, user_id=user_id, log_date=log_date)
    deleted = delete_day_entry_by_id(db, day_log, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")
    entries = list_day_entries(db, day_log)
    return build_day_detail(day_log, entries)


@app.post("/api/reports/summary", response_model=ReportSummaryOut)
def api_reports_summary(
    user_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    safe_days = min(max(days, 1), 365)
    date_to = date.today()
    date_from = date.fromordinal(date_to.toordinal() - (safe_days - 1))
    return report_for_range(db, user_id=user_id, date_from=date_from, date_to=date_to)


@app.get("/api/reports/summary", response_model=ReportSummaryOut)
def api_reports_summary_get(
    user_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    return api_reports_summary(user_id=user_id, days=days, db=db, x_user_pin=x_user_pin)


@app.get("/api/reports/range", response_model=ReportSummaryOut)
def api_reports_range(
    user_id: int,
    date_from: date,
    date_to: date,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    return report_for_range(db, user_id=user_id, date_from=date_from, date_to=date_to)


@app.get("/api/reports/month", response_model=ReportSummaryOut)
def api_reports_month(
    user_id: int,
    month: str,
    db: Session = Depends(get_db),
    x_user_pin: str = Header(..., alias="X-User-PIN"),
):
    if not require_user_pin(db, user_id, x_user_pin):
        raise HTTPException(status_code=401, detail="Invalid PIN")
    try:
        date_from, date_to = parse_month_to_range(month)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Niepoprawny format month. Uzyj YYYY-MM.") from exc
    return report_for_range(db, user_id=user_id, date_from=date_from, date_to=date_to)


@app.post("/api/chat/message", response_model=ChatResponseOut)
def api_chat_message(payload: ChatMessageIn, db: Session = Depends(get_db), x_user_pin: str = Header(..., alias="X-User-PIN")):
    user = require_user_pin(db, payload.user_id, x_user_pin)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid PIN")

    raw_user_message = payload.message.strip()

    def reply(day_log, *, text: str, warnings: list[str] | None = None) -> ChatResponseOut:
        response = ChatResponseOut(
            reply=text,
            log_date=day_log.log_date,
            total_kcal=round(day_log.total_kcal, 1),
            target_kcal=round(day_log.daily_kcal_target_snapshot, 1),
            total_carbs_g=round(day_log.total_carbs_g, 1),
            total_fat_g=round(day_log.total_fat_g, 1),
            total_protein_g=round(day_log.total_protein_g, 1),
            status=day_log.status,
            balance_mode=bool(day_log.balance_mode),
            warnings=warnings or [],
        )
        log_chat_interaction(user, raw_user_message, response_payload=response.model_dump(mode="json"))
        return response

    normalized = " ".join(raw_user_message.lower().split())
    current_day = get_or_create_day_log(db, user_id=payload.user_id, log_date=date.today())

    if normalized in {"pomoc", "help", "co umiesz"}:
        recalculate_day_totals(db, current_day)
        return reply(current_day, text=help_text())

    if normalized in COMMAND_SHOW_TODAY or normalized in COMMAND_SUMMARY:
        recalculate_day_totals(db, current_day)
        entries = list_day_entries(db, current_day)
        return reply(current_day, text=format_day_overview(current_day, entries))

    if normalized in COMMAND_UNDO:
        deleted = undo_last_entry(db, current_day)
        recalculate_day_totals(db, current_day)
        text = "Usunalem ostatni wpis." if deleted else "Brak wpisow do usuniecia."
        return reply(current_day, text=text)

    delete_match = DELETE_POSITION_PATTERN.search(raw_user_message)
    if delete_match:
        position = int(delete_match.group(1))
        deleted = delete_day_entry_by_position(db, current_day, position)
        recalculate_day_totals(db, current_day)
        if not deleted:
            return reply(
                current_day,
                text=f"Nie znalazlem pozycji nr {position}. Uzyj 'pokaz dzis', aby zobaczyc aktualna numeracje.",
            )
        entries = list_day_entries(db, current_day)
        return reply(
            current_day,
            text=f"Usunalem pozycje nr {position}: {format_entry_summary(deleted)}.\n" + format_day_overview(current_day, entries),
        )

    try:
        parsed = parse_template_message(raw_user_message)
    except ValueError as exc:
        recalculate_day_totals(db, current_day)
        return reply(current_day, text=str(exc))

    target_date = parsed.log_date or date.today()
    target_day = get_or_create_day_log(db, user_id=payload.user_id, log_date=target_date)
    target_day.status = "open"
    entry = create_day_entry(db, target_day, parsed)
    recalculate_day_totals(db, target_day)

    if entry.entry_type == "weight":
        message = f"Zapisalem wage dla dnia {target_day.log_date}: {entry.weight_kg:.1f} kg."
    elif entry.entry_type == "waist":
        message = f"Zapisalem obwod pasa dla dnia {target_day.log_date}: {entry.waist_cm:.1f} cm."
    else:
        message = f"Zapisalem wpis: {entry.entry_label}. " + format_entry_summary(entry)

    if target_day.balance_mode:
        message += "\nBilans dnia zastępuje sumę posilkow dla tego dnia."

    return reply(target_day, text=message)
