import mimetypes
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import clock, plan, services
from .config import settings
from .db import SessionLocal, healthcheck, init_db
from .models import User
from .schemas import (
    AuthVerifyIn,
    AuthVerifyOut,
    ChatMessageIn,
    ChatResponseOut,
    DayDetailOut,
    DaySummaryOut,
    EntryCreateIn,
    EntryDuplicateIn,
    EntryMoveIn,
    EntryUpdateIn,
    PlanApplyIn,
    PlanStatusOut,
    ProfilePreviewOut,
    PinChangeIn,
    ProfileIn,
    ProfileOut,
    ReportSummaryOut,
    UserCreate,
    UserOut,
)

FRONTEND_DIR = Path(settings.frontend_dir)
# Typy, ktorych brakuje w domyslnej bazie mimetypes (przy X-Content-Type-Options: nosniff musza byc poprawne).
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("application/manifest+json", ".webmanifest")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

if settings.cors_origin:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.cors_origin.split(",") if origin.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'",
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(services.InputError)
async def input_error_handler(_request: Request, exc: services.InputError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(services.ConflictError)
async def conflict_error_handler(_request: Request, exc: services.ConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(services.NotFoundError)
async def not_found_handler(_request: Request, exc: services.NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


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


AUTH_FAILED_DETAIL = "Sesja wygasła albo PIN jest niepoprawny – odblokuj ponownie."


def authenticate(db: Session, user_id: int, x_user_pin: str | None, authorization: str | None) -> User:
    """Token sesji (Authorization: Bearer) albo PIN (X-User-PIN). Token nie wymaga liczenia PBKDF2."""
    user = None
    if authorization and authorization.lower().startswith("bearer "):
        user = services.user_from_session(db, user_id, authorization[7:].strip())
    elif x_user_pin:
        user = services.require_user_pin(db, user_id, x_user_pin)
    if not user:
        raise HTTPException(status_code=401, detail=AUTH_FAILED_DETAIL)
    return user


def current_user(
    user_id: int,
    db: Session = Depends(get_db),
    x_user_pin: str | None = Header(None, alias="X-User-PIN"),
    authorization: str | None = Header(None),
) -> User:
    """user_id pochodzi ze sciezki (/users/{user_id}) albo z query (?user_id=)."""
    return authenticate(db, user_id, x_user_pin, authorization)


PROFILE_REQUIRED_DETAIL = "Uzupełnij profil (płeć, wiek, wzrost, waga, aktywność, cel) – bez niego CALICO nie może wyliczyć planu."


def profiled_user(user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    """Uzytkownik z uzupelnionym profilem - wymagane dla wszystkich danych dziennika, raportow i planu."""
    if not services.is_profile_complete(db, user.id):
        raise HTTPException(status_code=428, detail=PROFILE_REQUIRED_DETAIL)
    return user


# --- system ---------------------------------------------------------------------


@app.get("/health")
def health():
    return {"ok": healthcheck()}


@app.get("/api/meta")
def api_meta():
    return {"today": clock.today(), "timezone": settings.app_timezone}


# --- uzytkownicy i profil -------------------------------------------------------


@app.get("/api/users", response_model=list[UserOut])
def api_list_users(db: Session = Depends(get_db)):
    return services.list_users(db)


@app.post("/api/users", response_model=UserOut)
def api_create_user(payload: UserCreate, db: Session = Depends(get_db)):
    return services.create_user(db, payload.display_name, payload.pin)


@app.delete("/api/users/{user_id}", response_model=AuthVerifyOut)
def api_delete_user(user: User = Depends(current_user), db: Session = Depends(get_db)):
    services.delete_user(db, user)
    return AuthVerifyOut(ok=True)


@app.post("/api/users/{user_id}/pin", response_model=AuthVerifyOut)
def api_change_pin(payload: PinChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    services.change_user_pin(db, user, payload.new_pin)
    token, expires_at = services.issue_session(db, user)  # stare tokeny przestaja dzialac
    return AuthVerifyOut(ok=True, token=token, expires_at=expires_at)


@app.post("/api/auth/verify", response_model=AuthVerifyOut)
def api_verify_auth(payload: AuthVerifyIn, db: Session = Depends(get_db)):
    user = services.require_user_pin(db, payload.user_id, payload.pin)
    if not user:
        raise HTTPException(status_code=401, detail="Niepoprawny PIN")
    token, expires_at = services.issue_session(db, user)
    return AuthVerifyOut(ok=True, token=token, expires_at=expires_at)


def _profile_out(db: Session, user_id: int) -> ProfileOut:
    profile = services.get_profile(db, user_id)
    if not profile or profile.completed_at is None:
        return ProfileOut(user_id=user_id, is_complete=False)
    out = ProfileOut(
        user_id=user_id,
        is_complete=True,
        sex=profile.sex,
        age=profile.age,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        goal_type=profile.goal_type,
        goal_delta_pct=profile.goal_delta_pct,
        daily_kcal_target=profile.daily_kcal_target,
        plan_tdee_kcal=profile.plan_tdee_kcal,
        plan_started_on=profile.plan_started_on,
    )
    latest = services.latest_weight_entry(db, user_id)
    if latest:
        out.current_weight_kg = latest.weight_kg
        out.current_weight_date = latest.day_log.log_date
    return out


@app.get("/api/profile/{user_id}", response_model=ProfileOut)
def api_get_profile(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _profile_out(db, user.id)


@app.put("/api/profile/{user_id}", response_model=ProfileOut)
def api_put_profile(payload: ProfileIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    services.upsert_profile(db, user_id=user.id, payload=payload)
    return _profile_out(db, user.id)


@app.post("/api/profile/{user_id}/preview", response_model=ProfilePreviewOut)
def api_profile_preview(payload: ProfileIn, user: User = Depends(current_user)):
    """Podglad wyliczen dla formularza profilu - nic nie zapisuje, dziala takze przed uzupelnieniem profilu."""
    tdee = services.calculate_tdee(payload)
    target = services.calculate_target(payload)
    return ProfilePreviewOut(
        bmr_kcal=round(services.calculate_bmr(payload), 0),
        tdee_kcal=tdee,
        target_kcal=target,
        delta_kcal=round(target - tdee, 0),
    )


@app.get("/api/profile/{user_id}/plan", response_model=PlanStatusOut)
def api_plan_status(user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    return plan.evaluate_plan(db, user.id)


@app.post("/api/profile/{user_id}/plan/apply", response_model=PlanStatusOut)
def api_plan_apply(payload: PlanApplyIn, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    return plan.apply_suggestion(db, user.id, payload.target_kcal)


# --- dni i wpisy ------------------------------------------------------------------


@app.get("/api/days/current", response_model=DaySummaryOut)
def api_current_day(user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    return services.day_totals_out(db, user.id, clock.today())


@app.get("/api/days", response_model=list[DaySummaryOut])
def api_list_days(
    limit: int = 30,
    date_from: date | None = None,
    date_to: date | None = None,
    user: User = Depends(profiled_user),
    db: Session = Depends(get_db),
):
    """Dni z wpisami (od najnowszego); opcjonalnie w zakresie dat - np. miesiac dla kalendarza."""
    return services.list_days(db, user_id=user.id, limit=limit, date_from=date_from, date_to=date_to)


@app.get("/api/days/{log_date}", response_model=DayDetailOut)
def api_day_detail(log_date: date, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    return services.day_detail_out(db, user.id, log_date)


@app.post("/api/days/{log_date}/entries", response_model=DayDetailOut)
def api_create_entry(log_date: date, payload: EntryCreateIn, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    parsed = services.entry_input_from_values(payload, log_date=log_date)
    _entry, day_log, _replaced = services.create_entry(db, user.id, parsed)
    return services.day_detail_out(db, user.id, day_log.log_date)


@app.patch("/api/days/{log_date}/entries/{entry_id}", response_model=DayDetailOut)
def api_update_entry(
    log_date: date,
    entry_id: int,
    payload: EntryUpdateIn,
    user: User = Depends(profiled_user),
    db: Session = Depends(get_db),
):
    entry = services.get_entry(db, user.id, log_date, entry_id)
    if payload.entry is not None:
        parsed = services.entry_input_from_values(payload.entry)
    elif payload.source_text is not None:
        parsed = services.parse_template_message(payload.source_text)
        parsed.log_date = None  # do zmiany dnia sluzy /move
    else:
        raise services.InputError("Podaj 'entry' albo 'source_text'.")
    services.update_entry(db, user.id, entry, parsed)
    return services.day_detail_out(db, user.id, log_date)


@app.post("/api/days/{log_date}/entries/{entry_id}/move", response_model=DayDetailOut)
def api_move_entry(
    log_date: date,
    entry_id: int,
    payload: EntryMoveIn,
    user: User = Depends(profiled_user),
    db: Session = Depends(get_db),
):
    entry = services.get_entry(db, user.id, log_date, entry_id)
    target_day = services.move_entry(db, user.id, entry, payload.target_date)
    return services.day_detail_out(db, user.id, target_day.log_date)


@app.post("/api/days/{log_date}/entries/{entry_id}/duplicate", response_model=DayDetailOut)
def api_duplicate_entry(
    log_date: date,
    entry_id: int,
    payload: EntryDuplicateIn,
    user: User = Depends(profiled_user),
    db: Session = Depends(get_db),
):
    entry = services.get_entry(db, user.id, log_date, entry_id)
    _copy, target_day = services.duplicate_entry(db, user.id, entry, payload.target_date)
    return services.day_detail_out(db, user.id, target_day.log_date)


@app.delete("/api/days/{log_date}/entries/{entry_id}", response_model=DayDetailOut)
def api_delete_entry(log_date: date, entry_id: int, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    services.delete_entry(db, user.id, log_date, entry_id)
    return services.day_detail_out(db, user.id, log_date)


@app.post("/api/days/{log_date}/undo", response_model=DayDetailOut)
def api_undo_entry(log_date: date, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    if not services.undo_last_entry(db, user.id, log_date):
        raise services.NotFoundError("Brak wpisów do cofnięcia w tym dniu.")
    return services.day_detail_out(db, user.id, log_date)


@app.post("/api/days/{log_date}/clear", response_model=DayDetailOut)
def api_clear_day(log_date: date, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    services.clear_day(db, user.id, log_date)
    return services.day_detail_out(db, user.id, log_date)


# --- raporty i eksport ---------------------------------------------------------------


@app.get("/api/reports/summary", response_model=ReportSummaryOut)
def api_reports_summary(days: int = 7, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    date_from, date_to = services.last_days_range(days)
    return services.report_for_range(db, user_id=user.id, date_from=date_from, date_to=date_to)


@app.get("/api/reports/range", response_model=ReportSummaryOut)
def api_reports_range(date_from: date, date_to: date, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    return services.report_for_range(db, user_id=user.id, date_from=date_from, date_to=date_to)


@app.get("/api/reports/month", response_model=ReportSummaryOut)
def api_reports_month(month: str, user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    date_from, date_to = services.parse_month_to_range(month)
    return services.report_for_range(db, user_id=user.id, date_from=date_from, date_to=date_to)


@app.get("/api/export")
def api_export(user: User = Depends(profiled_user), db: Session = Depends(get_db)):
    content = "﻿" + services.export_entries_csv(db, user.id)
    file_name = f"calico-{user.slug}-{clock.today().isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


# --- czat -----------------------------------------------------------------------------


@app.post("/api/chat/message", response_model=ChatResponseOut)
def api_chat_message(
    payload: ChatMessageIn,
    db: Session = Depends(get_db),
    x_user_pin: str | None = Header(None, alias="X-User-PIN"),
    authorization: str | None = Header(None),
):
    user = authenticate(db, payload.user_id, x_user_pin, authorization)
    if not services.is_profile_complete(db, user.id):
        raise HTTPException(status_code=428, detail=PROFILE_REQUIRED_DETAIL)

    result = services.handle_chat_message(db, user.id, payload.message)
    totals = services.day_totals_out(db, user.id, result.log_date)
    return ChatResponseOut(**totals.model_dump(), kind=result.kind, reply=result.text)


# --- frontend (musi byc na koncu, po trasach API) ------------------------------------

if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
