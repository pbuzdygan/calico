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
  - `index.html` — sprite ikon (`<symbol id="i-…">`), ekran blokady, powłoka z nawigacją, 5 widoków (`#view-today|log|progress|goals|settings`, routing przez `location.hash`), dolne panele `<dialog class="sheet">`
  - `js/` — moduły ES bez bundlera (punkt wejścia `js/main.js`, opis modułów w jego nagłówku): `config.js` (stałe), `state.js` (`el`, `state`), `util.js`, `ui.js` (toasty, `withBusy`, panele), `api.js` (`fetchJSON`, sesja), `auth.js` (blokada, użytkownicy), `nav.js`, `charts.js` (SVG), `views/{today,log,progress,goals,settings}.js`, `entry-sheet.js` (panel wpisu, akcje pozycji), `profile-form.js` (korekta celu, onboarding D8). Nowy plik JS dopisz do `SHELL` w `sw.js` i podbij `CACHE`
  - `styles.css` — tokeny kolorów z `docs/UI design.md` (`:root`), karty hero/metric/info, mobile-first, boczna nawigacja od 960 px
  - `manifest.json`, `sw.js`, `icons/` (generowane: `scripts/generate_icons.py` z `branding/`), `fonts/` (Inter, OFL)
- Infra: jeden kontener (`docker-compose.yml` → `backend/Dockerfile`, build context = katalog główny repo)

## Aktualny stan i backlog

**Zanim zaczniesz: przeczytaj `docs/decisions.md`.** Zawiera obowiązujące decyzje właściciela (`D1`–`D12`, już rozstrzygnięte) i zadania otwarte. Historia (pierwotny przegląd, zrobione zadania) jest w git – odnośniki w nagłówku tego pliku.

Kluczowe decyzje produktowe (nie zmieniaj bez zgody właściciela):
- brak statusu dnia (otwarty/zamknięty) — usunięty (D1),
- **D2b: aktualna waga ≠ automatyczna zmiana celu.** Cel kcal to plan zmieniany tylko jawnie (zapis profilu albo akceptacja sugestii z `app/plan.py`). Wpisy `Waga` służą do monitorowania trendu. Nie dodawaj automatycznego przeliczania celu po ważeniu („spirala deficytu”),
- zmiana celu aktualizuje cel dziś i w przyszłych dniach, nie w przeszłych (D3),
- **D8: profil bez wartości domyślnych, uzupełnienie wymuszone przy pierwszym logowaniu.** Nowe endpointy danych muszą używać zależności `profiled_user` (428 bez profilu), a nie `current_user`,
- uwierzytelnienie: `authenticate()` w `main.py` (token `Authorization: Bearer` albo `X-User-PIN`); frontend wysyła wyłącznie token (`userHeaders()`), sesja w `sessionStorage` (`calico.session`) – nigdy nie zapisuj PIN-u w przeglądarce,
- polskie znaki w UI i szablonach (D4); parser akceptuje też zapis bez nich,
- **D12: aplikacja dwujęzyczna PL/EN.** Polski jest językiem źródłowym, angielski to słownik. Każdy nowy tekst od razu w obu językach (zasady w „Zasady pracy”),
- wpisy maks. na jutro, nie wcześniej niż 2000-01-01 (D5),
- tylko LAN (D6),
- **D9: brak trybu administratora i logów diagnostycznych** – usunięte w całości; nie przywracaj bez zgody właściciela.
- **D10: brak użytkownika i PIN-u domyślnego.** Pierwszy start = ekran „Utwórz użytkownika”; nie dodawaj bootstrapu konta ani `DEFAULT_USER_PIN`.

## Uruchamianie

```bash
cp .env.example .env
docker compose up --build -d      # http://localhost:8080, pierwszy start: utwórz użytkownika (D10)
docker compose logs calico --tail=100
```

Testy (lokalnie zwykle nie ma Pythona z zależnościami — używaj kontenera):

```bash
cd backend
docker run --rm -v "$PWD:/app" -w /app -e PYTHONPATH=/app python:3.12-slim \
  sh -c "pip install -q -r requirements.txt -r requirements-dev.txt && pytest -q -p no:cacheprovider"
```

Sprawdzenie składni frontendu: `for f in frontend/js/*.js frontend/js/views/*.js; do node --check "$f"; done`.

Wszystko naraz, tak jak CI (`.github/workflows/ci.yml`: ruff + pytest + `node --check`): `./scripts/check.sh`. Lint backendu: `ruff` (konfiguracja `backend/ruff.toml`) – nowy kod musi go przechodzić.

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
- Zmiana kontraktu API wymaga w tym samym PR aktualizacji frontendu (`frontend/js/`), testów i sekcji API w `README.md`.
- Teksty UI i komunikaty API po polsku, z polskimi znakami, **zawsze z tłumaczeniem EN** (D12). Komentarze w kodzie bez wymagań co do znaków.
- i18n frontendu: tekst w JS tylko przez `t("Polski tekst {param}", { param })` (stały napis, bez template literal), stałe z etykietami przez `N_("…")` i `t(STAŁA[x])` przy użyciu, odmiana przez `plural(n, "1", "2-4", "5+")`. Statyczny tekst w `index.html` piszemy po prostu po polsku – tłumaczy go `applyTranslations()`; elementy, których nie tłumaczymy (np. nazwy języków), mają `data-i18n-skip`. Tłumaczenie dopisz do `frontend/js/locales/en.js` (klucz = polski tekst; odmiana: `"dzień|dni|dni": ["day", "days"]`).
- i18n backendu: komunikat dla użytkownika tylko przez `t("Polski tekst {param}", param=...)` z `app/i18n.py`, tłumaczenie w `app/locales/en.py`. Formatowanie liczb i dat przez `fmt_number`/`fmt_date` (zależne od języka). Dane zapisywane w bazie (etykiety, `source_text`) zostają po polsku – `canonical_source_text()`, `display_entry_label()` przy odczycie.
- Kontrola: `node scripts/check_i18n.mjs` i `tests/test_i18n.py` (CI, `scripts/check.sh`) – brak tłumaczenia, martwy wpis albo polski tekst z pominięciem `t()` to błąd. Nie obchodź ich – dopisz tłumaczenie.
- Frontend: każdy tekst z danych wstawiany do HTML przez `escapeHtml()` albo `textContent`. Komunikaty dla użytkownika przez `toast()`; akcje z przyciskami przez `withBusy()`.
- Nie commituj `.env`, baz `*.db` ani plików z `/data`.
- Po zakończeniu zadania usuń je z zadań otwartych w `docs/decisions.md`; nowa decyzja właściciela = nowy wiersz w sekcji 1.
