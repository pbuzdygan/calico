# CALICO

![Calico – Conscious habits. Real results.](branding/calico_banner.png)

CALICO to prosty dziennik kalorii, makroskładników, wagi i obwodu pasa. Wpisy dodaje się przez formularz albo przez wklejenie tekstowego szablonu. Aplikacja nie korzysta z AI ani parsera języka naturalnego. Przeznaczona do użytku domowego w sieci LAN.

## Co robi aplikacja

- prowadzi wpisy dzienne per użytkownik (PIN 4–8 cyfr),
- zapisuje: `Waga`, `Obwód pasa`, `Śniadanie`, `Obiad`, `Kolacja`, `Przekąska`, `Bilans dnia`,
- liczy sumę kcal i makro dnia oraz cel kcal (Mifflin-St Jeor × aktywność × korekta celu),
- `Dziennik`: edycja, duplikowanie, przenoszenie i usuwanie pozycji, cofanie ostatniej zmiany, czyszczenie dnia,
- `Raporty`: 7/30/90 dni, miesiąc, dowolny zakres — kalorie vs cel, bilans, najwyższy dzień, trend wagi (średnia 7-dniowa),
- eksport wszystkich wpisów do CSV.

## Interfejs

Mobile-first, ciemny motyw zgodny z brandingiem (`docs/UI design.md`): granatowe karty, akcenty cyan/teal, pierścień postępu jako główny motyw.

- **Dziś** – przycisk „Dodaj posiłek” w prawym górnym rogu, pierścień kalorii (spożycie / cel), makroskładniki (udział w energii), karty wagi i obwodu pasa z mini-wykresami, regularność 7 dni („w celu” = ±10% celu kcal), cel kaloryczny i rekomendacja z oceny planu.
- **Dziennik** – kalendarz miesięczny (kropka = dzień z wpisami: turkusowa – jedzenie, niebieska – tylko pomiary; klik wybiera dzień) oraz posiłki pogrupowane (Śniadanie, Obiad, Kolacja, Przekąski, Bilans dnia, Pomiary); dotknięcie pozycji otwiera akcje: edytuj, duplikuj, przenieś, usuń.
- **Postępy** – 1M/3M/6M/1R/Wszystko/Własny: wykres wagi (z trendem 7 dni), obwodu, kalorii na tle celu, regularność tygodnia, historia dni.
- **Cele** – aktualny plan, waga planu vs średnia, ocena planu i akceptacja sugestii.
- **Więcej** – profil i plan, zmiana PIN-u, eksport CSV, konto.

Nawigacja (Dziś, Postępy, Cele, Dziennik, Więcej): dolny pasek na telefonie, boczny panel od 960 px. Dodawanie i edycja w dolnych panelach. Font Inter (OFL) jest dołączony lokalnie (`frontend/fonts/`) – aplikacja nie pobiera nic z internetu.

### PWA i ikony

- `frontend/manifest.json`, `frontend/sw.js` (cache powłoki aplikacji; dane `/api` nigdy nie są cache'owane).
- Ikony w `frontend/icons/` generuje skrypt z plików w `branding/`:

```bash
docker run --rm -v "$PWD:/repo" -w /repo python:3.12-slim \
  sh -c "pip install -q pillow && python scripts/generate_icons.py"
```

- Instalacja jako aplikacja (Android/Chrome, desktop) wymaga HTTPS albo `localhost` – przeglądarki nie uruchamiają service workera po zwykłym `http://` w sieci LAN. Na iOS „Dodaj do ekranu początkowego” działa także po HTTP (ikona `apple-touch-icon`).

## Najważniejsze reguły

- **Profil jest obowiązkowy i nie ma wartości domyślnych.** Nowy użytkownik po pierwszym odblokowaniu PIN-em musi uzupełnić profil: płeć, wiek, wzrost, aktualną wagę, aktywność, cel i korektę celu. Okna nie da się zamknąć ani pominąć, można jedynie zmienić użytkownika. Do tego czasu API danych zwraca `428`.

- „Dzisiaj” liczone jest w strefie `APP_TIMEZONE` (domyślnie `Europe/Warsaw`).
- Data wpisu: od `2000-01-01` do jutra włącznie.
- `Waga`, `Obwód pasa`, `Bilans dnia`: jeden wpis na dzień, nowy nadpisuje poprzedni. Edycja/przeniesienie, które utworzyłoby drugi taki wpis, zwraca błąd 409.
- Posiłki: dowolnie wiele w ciągu dnia, etykiety `Śniadanie`, `Śniadanie Drugie`, `Obiad Drugi`, `Kolacja Druga`…
- `Bilans dnia` zastępuje sumę posiłków z tego dnia.
- Cel kcal to **plan**, a nie wynik wzoru po każdym ważeniu. Zmienia się tylko jawnie:
  - zapis profilu = nowy plan liczony wzorem z „wagi planu” (zapis ze zmienioną wagą tworzy też dzisiejszy wpis `Waga`),
  - akceptacja sugestii z karty „Ocena planu” (zakładka `Cele`).
- Wpisy `Waga` służą do monitorowania: profil pokazuje aktualną wagę obok wagi planu, ale cel się nie zmienia.
- Ocena planu (`app/plan.py`): trend masy z regresji pomiarów od startu planu (min. 4 pomiary z 14 dni), porównany z tempem wynikającym z planu. W zakresie → cel bez zmian, nawet jeśli szacowane TDEE spadło. Poza zakresem → przez pierwsze 21 dni „obserwuj”, potem sugestia korekty o 100–200 kcal (nie poniżej 1500 kcal dla mężczyzn / 1200 kcal dla kobiet). Gdy wpisy jedzenia pokrywają ≥ 70% dni, TDEE jest szacowane także z faktycznego spożycia i zmiany masy.
- Zmiana celu aktualizuje cel dnia dzisiejszego i przyszłych; przeszłe dni zachowują swój cel.
- Cele makro (g) są domyślnie wyliczane z celu kcal dnia: białko 25% i tłuszcze 30% energii, węglowodany dopełniają resztę (stałe `MACRO_AUTO_*` w `services.py`). Własne cele w zakładce `Cele` są opcjonalne – każde pole osobno, puste = automatycznie; gdy wpiszesz tylko białko lub tłuszcze, węglowodany dalej dopełniają cel kcal. Zmiana celów makro nie zmienia planu kcal. Na „Dziś” paski pokazują postęp względem celu; przekroczenie jest bursztynowe.
- Raporty liczą średnie i dni powyżej/poniżej celu tylko z dni, w których jest wpis jedzenia (posiłek lub bilans).
- Zakresy wartości: kcal 0–10 000, makro 0–1 000 g, waga 30–300 kg, obwód 30–250 cm.

## Szablony tekstowe (zakładka Dzień → „Wklej tekst”)

```text
Waga: 82,4 kg
```

```text
Obwód pasa: 91 cm
```

```text
Śniadanie
Ilość kalorii: 540
Węglowodany: 48
Tłuszcze: 18
Białko: 32
```

Nagłówki: `Śniadanie`, `Obiad`, `Kolacja`, `Przekąska`, `Bilans dnia`. Polskie znaki są opcjonalne (`Sniadanie`, `Ilosc kalorii` też działa), liczby z przecinkiem lub kropką, jednostki opcjonalne.

Inny dzień — pierwsza linia `Data:` (`RRRR-MM-DD`, `DD.MM.RRRR`, `DD-MM-RRRR`, `DD/MM/RRRR`):

```text
Data: 2026-08-03
Kolacja
Ilość kalorii: 610
Węglowodany: 40
Tłuszcze: 22
Białko: 38
```

Komendy tekstowe (cała wiadomość): `pokaż dziś`, `cofnij ostatni`, `usuń 2`, `pomoc`.

## Start

```bash
cp .env.example .env
docker compose up --build -d
```

Otwórz `http://localhost:8080`. Przy pierwszym starcie nie ma żadnego użytkownika ani PIN-u domyślnego – aplikacja prosi o utworzenie pierwszego użytkownika (nazwa i PIN), a potem wymusza uzupełnienie profilu. PIN można zmienić w zakładce `Więcej`.

Istniejące instalacje zachowują swoich użytkowników (także dawnego „Domyślnego Użytkownika” – można go usunąć po założeniu własnego konta). Klucz `DEFAULT_USER_PIN` w `.env` jest ignorowany i można go usunąć.

Aplikacja działa w jednym kontenerze: FastAPI serwuje API i pliki frontendu. Dane są w wolumenie `calico_data` (`/data/calico.db`).

Aktualizacja z wersji z Caddy (dwa kontenery `backend` + `proxy`):

```bash
docker compose up --build -d --remove-orphans
```

Wolumen z danymi zostaje ten sam. Przy pierwszym starcie baza jest migrowana automatycznie (wersja schematu w tabeli `app_meta`, klucz `schema_version`).

## Konfiguracja (`.env`)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `APP_TIMEZONE` | `Europe/Warsaw` | strefa, w której liczony jest „dzisiejszy” dzień |
| `SQLITE_PATH` | `/data/calico.db` | ścieżka bazy |
| `CORS_ORIGIN` | pusty | pusty = brak CORS (frontend i API na tym samym adresie) |
| `ALLOW_SIGNUP` | `true` | `false` = nowe konta można zakładać tylko przy pierwszym starcie (gdy nie ma żadnego użytkownika); `POST /api/users` zwraca wtedy `403` |
| `SESSION_TTL_HOURS` | `12` | jak długo ważna jest sesja po odblokowaniu PIN-em |
| `SESSION_SECRET` | pusty | klucz podpisu sesji; pusty = generowany automatycznie i zapisany w bazie |

## API

Wszystkie endpointy danych wymagają parametru `user_id` (query albo ścieżka) oraz uwierzytelnienia: `Authorization: Bearer <token>` (token z `POST /api/auth/verify`, ważny `SESSION_TTL_HOURS`) albo nagłówka `X-User-PIN`. Błędy: `401` zły PIN, `404` brak obiektu, `409` konflikt (np. drugi wpis `Waga` w dniu), `422` niepoprawne dane, `428` profil nieuzupełniony (dotyczy dni, wpisów, raportów, planu, eksportu i czatu).

Użytkownicy i profil:

- `GET /api/users` (pusta lista = pierwszy start), `POST /api/users` — `{"display_name": "Ala", "pin": "2468"}` (`403`, gdy `ALLOW_SIGNUP=false` i istnieje już użytkownik), `DELETE /api/users/{user_id}`
- `POST /api/users/{user_id}/pin` — `{"new_pin": "5678"}`; unieważnia stare tokeny i zwraca nowy
- `POST /api/auth/verify` — `{"user_id": 1, "pin": "1234"}` → `{"ok": true, "token": "…", "expires_at": "…"}`
- `GET|PUT /api/profile/{user_id}` — `is_complete=false` i puste pola, dopóki profil nie zostanie zapisany; `PUT` wymaga wszystkich pól. `weight_kg` to waga planu, `current_weight_kg` to ostatni pomiar. `macro_targets`: obowiązujące cele `protein_g`, `fat_g`, `carbs_g` oraz `manual_*` (null = automatycznie)
- `PUT /api/profile/{user_id}/macros` — `{"protein_g": 170}`; pola opcjonalne (brak/null = automatycznie, `{}` przywraca automatyczne), zakresy: białko 0–500, tłuszcze 0–400, węglowodany 0–1000 g
- `POST /api/profile/{user_id}/preview` — podgląd BMR/TDEE/celu dla danych z formularza (bez zapisu, działa przed uzupełnieniem profilu)
- `GET /api/profile/{user_id}/plan` — ocena planu (status, trend, TDEE, sugestia)
- `POST /api/profile/{user_id}/plan/apply` — `{"target_kcal": 2460}` akceptuje bieżącą sugestię (409, jeśli się zmieniła)

Dni i wpisy (odczyt nigdy nie tworzy dnia w bazie):

- `GET /api/days/current?user_id=`
- `GET /api/days?user_id=&limit=&date_from=&date_to=` — tylko dni z wpisami (zakres dat używa kalendarz Dziennika)
- `GET /api/days/{date}?user_id=` — sumy dnia, wpisy oraz cele makro dnia `target_protein_g`, `target_fat_g`, `target_carbs_g` (liczone od celu kcal dnia; także w `GET /api/days` i `/api/days/current`)
- `POST /api/days/{date}/entries?user_id=` — `{"entry_type": "lunch", "kcal": 600, "carbs_g": 60, "fat_g": 20, "protein_g": 40}` lub `{"entry_type": "weight", "weight_kg": 82.4}`
- `PATCH /api/days/{date}/entries/{id}?user_id=` — `{"entry": {...}}` albo `{"source_text": "..."}`
- `POST /api/days/{date}/entries/{id}/move?user_id=` — `{"target_date": "2026-06-14"}`
- `POST /api/days/{date}/entries/{id}/duplicate?user_id=` — `{"target_date": null}` (null = ten sam dzień)
- `DELETE /api/days/{date}/entries/{id}?user_id=`
- `POST /api/days/{date}/undo?user_id=` — usuwa ostatnio dodaną/zmienioną pozycję dnia
- `POST /api/days/{date}/clear?user_id=`

Raporty i eksport:

- `GET /api/reports/summary?user_id=&days=7`
- `GET /api/reports/range?user_id=&date_from=&date_to=` (maks. 3660 dni)
- `GET /api/reports/month?user_id=&month=RRRR-MM`
- `GET /api/export?user_id=` — CSV

Czat tekstowy: `POST /api/chat/message` — odpowiedź ma pole `kind`: `saved`, `info` albo `error`.

Pozostałe: `GET /health`, `GET /api/meta` (dzisiejsza data serwera, strefa, `allow_signup`).

## Testy

```bash
cd backend
docker run --rm -v "$PWD:/app" -w /app -e PYTHONPATH=/app python:3.12-slim \
  sh -c "pip install -q -r requirements.txt -r requirements-dev.txt && pytest -q -p no:cacheprovider"
```

## Bezpieczeństwo

- Aplikacja jest przeznaczona do sieci domowej. Nie wystawiaj jej do internetu bez reverse proxy z TLS i dodatkowego uwierzytelnienia.
- PIN haszowany PBKDF2-SHA256 (120 tys. iteracji), porównanie w czasie stałym.
- Po odblokowaniu przeglądarka dostaje podpisany token sesji (HMAC-SHA256, ważny 12 h) i trzyma go w `sessionStorage`: sesja przetrwa przeładowanie karty (np. gdy telefon uśpi przeglądarkę w tle), znika po zamknięciu karty i po wylogowaniu. PIN nie jest nigdzie zapisywany. Zmiana PIN-u unieważnia wszystkie wcześniejsze sesje.
- Nagłówki `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
- SQLite w trybie `WAL`, `foreign_keys=ON`; sekrety poza repo (`.env` w `.gitignore`).

## Dokumentacja projektu

- `docs/review-2026-09-30.md` — przegląd, decyzje produktowe i backlog (źródło prawdy dla dalszych prac),
- `AGENTS.md` — instrukcje dla agentów AI,
- `docs/ui-expansion-plan.md` — plan historyczny,
- `docs/UI design.md` — system wizualny i zasady UI (źródło prawdy dla wyglądu),
- `docs/mockups/` — wcześniejsze mockupy UI (historyczne).
