# AGENTS.md — instrukcje dla agentów AI (Codex, Claude Code i inne)

## Projekt

CALICO — dziennik kalorii, makroskładników, wagi i obwodu pasa. Wpisy przez formularz albo tekstowe szablony (bez AI/NLP), PIN per użytkownik. Użytek domowy, LAN.

- Backend: FastAPI + SQLAlchemy 2 + SQLite (`backend/app/`)
  - `main.py` — endpointy (cienkie), zależność `current_user`, mapowanie błędów domenowych (`InputError`→422, `ConflictError`→409, `NotFoundError`→404), serwowanie frontendu (`StaticFiles`)
  - `services.py` — cała logika domenowa: parser szablonów, walidacja, wpisy, przeliczanie dnia (`refresh_day`), synchronizacja wagi profilu, raporty, eksport, obsługa czatu
  - `plan.py` — ocena planu kalorycznego (trend masy, TDEE szacowane i z obserwacji, sugestia korekty celu); progi jako stałe na górze pliku
  - `clock.py` — jedyne źródło „teraz” i „dziś” (strefa `APP_TIMEZONE`); w testach podmieniane `clock.now_utc`
  - `db.py` — silnik, bootstrap, wersjonowane migracje (`MIGRATIONS`, klucz `schema_version` w `app_meta`)
  - `models.py`, `schemas.py`, `security.py`
- Frontend: vanilla JS/HTML/CSS bez bundlera, serwowany przez FastAPI
  - `index.html` — sprite ikon (`<symbol id="i-…">`), ekran blokady, powłoka z nawigacją, 5 widoków (`#view-today|log|progress|goals|more`, routing przez `location.hash`), dolne panele `<dialog class="sheet">`
  - `main.js` — sekcje: API, sesja/blokada, nawigacja, wykresy SVG (pierścień, sparkline, linia, słupki), widoki, panel wpisu, kalendarz dziennika, onboarding (D8), korekta celu
  - `styles.css` — tokeny kolorów z `docs/UI design.md` (`:root`), karty hero/metric/info, mobile-first, boczna nawigacja od 960 px
  - `manifest.json`, `sw.js`, `icons/` (generowane: `scripts/generate_icons.py` z `branding/`), `fonts/` (Inter, OFL)
- Infra: jeden kontener (`docker-compose.yml` → `backend/Dockerfile`, build context = katalog główny repo)

## Aktualny stan i backlog

**Zanim zaczniesz: przeczytaj `docs/review-2026-09-30.md`.** Zawiera znaleziska (`BUG-xx`, `SEC-xx`, `UX-xx`, `TECH-xx`), decyzje właściciela (`D1`–`D7`, sekcja 8 — już rozstrzygnięte) i backlog (`T0.x` … `T3.x`) ze statusem. `docs/ui-expansion-plan.md` jest planem historycznym.

Kluczowe decyzje produktowe (nie zmieniaj bez zgody właściciela):
- brak statusu dnia (otwarty/zamknięty) — usunięty (D1),
- **D2b: aktualna waga ≠ automatyczna zmiana celu.** Cel kcal to plan zmieniany tylko jawnie (zapis profilu albo akceptacja sugestii z `app/plan.py`). Wpisy `Waga` służą do monitorowania trendu. Nie dodawaj automatycznego przeliczania celu po ważeniu („spirala deficytu”),
- zmiana celu aktualizuje cel dziś i w przyszłych dniach, nie w przeszłych (D3),
- **D8: profil bez wartości domyślnych, uzupełnienie wymuszone przy pierwszym logowaniu.** Nowe endpointy danych muszą używać zależności `profiled_user` (428 bez profilu), a nie `current_user`,
- polskie znaki w UI i szablonach (D4); parser akceptuje też zapis bez nich,
- wpisy maks. na jutro, nie wcześniej niż 2000-01-01 (D5),
- tylko LAN (D6),
- **D9: brak trybu administratora i logów diagnostycznych** – usunięte w całości; nie przywracaj bez zgody właściciela.

## Uruchamianie

```bash
cp .env.example .env
docker compose up --build -d      # http://localhost:8080, "Domyślny Użytkownik", PIN 1234
docker compose logs calico --tail=100
```

Testy (lokalnie zwykle nie ma Pythona z zależnościami — używaj kontenera):

```bash
cd backend
docker run --rm -v "$PWD:/app" -w /app -e PYTHONPATH=/app python:3.12-slim \
  sh -c "pip install -q -r requirements.txt -r requirements-dev.txt && pytest -q -p no:cacheprovider"
```

Sprawdzenie składni frontendu: `node --check frontend/main.js`.

## Wygląd (UI)

- **Źródło prawdy: `docs/UI design.md`.** Ciemny granat, akcenty cyan/teal, pierścień postępu jako motyw marki; bez jasnych teł, ilustracji i „wellness” palety.
- Kolory tylko przez tokeny z `:root` w `styles.css`. Czerwony wyłącznie dla usuwania i błędów; przekroczenie celu = bursztyn (`--warning`).
- Nowe elementy składaj z istniejących klas: `.card` (+ `.hero-card` / `.metric-card` / `.info-card`), `.btn` (`-primary`, `-cta`, `-quiet`, `-danger`), `.chip`, `.seg`, `.sheet`, `.stat`, `.kv`.
- Ikony: dopisz `<symbol>` do sprite'a w `index.html` (kontur, 24×24, `stroke="currentColor"`), użycie `icon("nazwa")` w JS.
- Komunikaty wewnątrz otwartego `<dialog>` pokazuj w polu statusu w panelu (toasty są pod warstwą modalną).
- Sprawdzaj widok 390 px i 1440 px; brak poziomego przewijania; cele dotyku ≥ 44 px.

## Zasady pracy

- Jedno zadanie z backlogu = jeden commit/PR na branchu `dev`. W opisie podaj ID zadania i znalezisk (np. `T2.3 / UX-04`).
- Zmiany backendu: najpierw test odtwarzający błąd lub opisujący funkcję (`backend/tests/`), potem kod. Wszystkie testy muszą przechodzić.
- Logika domenowa tylko w `services.py`; endpointy w `main.py` mają być cienkie.
- Każda mutacja wpisów musi kończyć się `refresh_day(...)` dla zmienionych dni.
- Cel kcal zmienia się wyłącznie przez `services.set_plan_target(...)`.
- Odczyty nie mogą tworzyć wierszy w bazie (`get_day_log`, nie `get_or_create_day_log`).
- „Dziś” zawsze przez `clock.today()`, nigdy `date.today()` / `datetime.utcnow()`.
- Zmiana schematu bazy = nowa pozycja w `MIGRATIONS` w `db.py` (idempotentna, działająca na istniejącej bazie). **Migracje piszemy czystym SQL-em** – model ORM zna kolumny z przyszłych migracji i zapytanie przez ORM wysypie się na starej bazie. Test `tests/test_migrations.py` migruje bazę z wersji `884cafa`; po dodaniu migracji zaktualizuj oczekiwane `schema_version`.
- Zmiana kontraktu API wymaga w tym samym PR aktualizacji frontendu (`main.js`), testów i sekcji API w `README.md`.
- Teksty UI i komunikaty API po polsku, z polskimi znakami. Komentarze w kodzie bez wymagań co do znaków.
- Frontend: każdy tekst z danych wstawiany do HTML przez `escapeHtml()` albo `textContent`. Komunikaty dla użytkownika przez `toast()`; akcje z przyciskami przez `withBusy()`.
- Nie commituj `.env`, baz `*.db` ani plików z `/data`.
- Po zakończeniu zadania zaktualizuj jego status w `docs/review-2026-09-30.md`.
