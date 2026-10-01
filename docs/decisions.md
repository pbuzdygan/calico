# CALICO — decyzje właściciela i zadania otwarte

Dokument roboczy dla ludzi i agentów AI (Claude Code, Codex itp.): obowiązujące decyzje produktowe i to, co jeszcze zostało do zrobienia. Opisuje tylko stan **aktualny**.

**Zasada utrzymania:** zadanie skończone → usuń je z sekcji 2 (szczegóły zostają w commicie). Nowa decyzja właściciela → dopisz wiersz w sekcji 1 z datą. Zadanie nieaktualne po decyzji → usuń i wspomnij numer decyzji w opisie commita. Nie zapisuj tu opisów naprawionych błędów ani historii — jest w git.

Historia: pierwotny przegląd kodu z 2026-09-30 (znaleziska `BUG-xx`, `SEC-xx`, `UX-xx`, `TECH-xx`): `git show b144e3b:docs/review-2026-09-30.md`; rejestr zrobionych zadań do T-I18N: `git show e365aa2:docs/review-2026-09-30.md`. Źródło prawdy dla wyglądu: `docs/UI design.md`.

---

## 1. Decyzje właściciela

| ID | Decyzja | Jak wdrożono |
|---|---|---|
| D1 | **Brak statusu dnia** (otwarty/zamknięty). | Migracja 1 usuwa `status`, `closed_at`; brak endpointów `close`/`reopen`. |
| D2b | **Aktualna waga ≠ automatyczna zmiana celu.** Trzy oddzielne wartości: cel planu, szacowane TDEE, obserwowany trend. Cel zmienia się tylko jawnie (zapis profilu albo akceptacja sugestii). | `app/plan.py`. Waga w profilu = waga planu (start); aktualna waga (ostatni wpis) tylko do odczytu. `GET /api/profile/{id}/plan`: trend z regresji pomiarów od startu planu (okno 28 dni, min. 4 pomiary z 14 dni), oczekiwane tempo `(cel − TDEE planu)·7/7700` ± tolerancja (max(50%, 0,25% masy/tydz.); limity: utrata ≤ 1%/tydz., przyrost ≤ 0,5%/tydz.), TDEE z obserwacji `średnie spożycie − tempo·7700` (gdy jedzenie pokrywa ≥ 70% dni). W zakresie → cel bez zmian. Poza zakresem < 21 dni planu → „obserwuj”. Dalej → sugestia korekty 100–200 kcal, nie poniżej 1500 (M) / 1200 (K). `POST .../plan/apply`: nowy cel, start planu = dziś, waga planu = średnia 7 dni. Progi to stałe w `plan.py`. |
| D3 | **Zmiana celu aktualizuje dziś i przyszłe dni**, przeszłe bez zmian. | `_apply_profile_target`: `log_date >= today`. |
| D4 | **Polskie znaki włączone** w UI, komunikatach API, etykietach i szablonach. Parser akceptuje też zapis bez znaków. | Etykiety `Śniadanie Drugie`, `Obiad Drugi`, `Kolacja Druga`; kanoniczny `source_text`. |
| D5 | **Wpisy od 2000-01-01 do jutra włącznie.** | `validate_log_date` dla wpisów, przenoszenia i duplikowania. |
| D6 | **Tylko LAN / dom.** Utwardzenie (lockout itp.) ma niski priorytet. | Jeden kontener, bez Caddy. |
| D7 | Plan rozbudowy UI z czasów parsera AI (`docs/ui-expansion-plan.md`) jest **nieaktualny**. | Usunięty z repo 2026-10-01 (historia: `git show e365aa2:docs/ui-expansion-plan.md`). |
| D8 | **Profil bez wartości domyślnych, uzupełnienie wymuszone** przy pierwszym logowaniu, nie da się pominąć. | `Profile.completed_at`; zależność `profiled_user` → `428` dla dni, wpisów, raportów, planu, eksportu i czatu. Frontend: niezamykalne okno „Uzupełnij profil”. Migracja 4 oznacza nigdy niezapisane profile jako niekompletne. |
| D9 | **Brak trybu administratora i logów diagnostycznych** — usunięte w całości. | Usunięte `diagnostics.py`, `/api/admin/*`, `ADMIN_PIN`, `DIAGNOSTICS_PATH`, panel w UI. Stare klucze w `.env` są ignorowane (`extra="ignore"`). |
| D10 | **Brak użytkownika i PIN-u domyślnego** (2026-10-01). Pierwszy start = ekran „Utwórz użytkownika” ze świadomie wybraną nazwą i PIN-em. | Usunięty bootstrap konta i `DEFAULT_USER_PIN`. Pusta lista z `GET /api/users` → ekran pierwszego startu. Istniejące bazy zachowują swoich użytkowników. Zastępuje wymuszanie zmiany PIN-u domyślnego (SEC-05). |
| D11 | **Bez automatycznej kopii zapasowej** (2026-10-01). Dane zabezpiecza użytkownik eksportem z UI; dochodzi import tego samego pliku. Plik = prosty formularz CSV „wiersz = dzień” (data, waga, obwód, kalorie, makro) do pobrania z UI jako pusty szablon; eksport ma ten sam wygląd. Import pomija dni, które mają już wpisy. | T-IO |
| D12 | **Aplikacja dwujęzyczna PL/EN** (2026-10-01), na razie bez kolejnych języków. Każda zmiana i nowa funkcja od razu w obu językach, także szablon importu i eksport CSV. | Polski = język źródłowy (klucz), słowniki `frontend/js/locales/en.js` i `backend/app/locales/en.py`; `t()`/`N_()`/`plural()` we frontendzie, `t()` w backendzie (`Accept-Language`); język na urządzeniu i na koncie (migracja 8); strażnicy w CI: `scripts/check_i18n.mjs`, `tests/test_i18n.py`. Zasady w AGENTS.md. |

---

## 2. Zadania otwarte

Kolejność = rekomendowana kolejność realizacji. Jedno zadanie = jeden commit/PR na `dev`.

| ID | Zadanie | Kryterium akceptacji | Uwagi |
|---|---|---|---|
| T2.6 | **Kalibracja progów planu** w `plan.py` (tolerancja, 21/28 dni, krok 100–200 kcal) na realnych danych; ewentualnie podpowiedź oceny planu na „Dziś”. | — | najwcześniej po kilku tygodniach używania |

Świadomie **nie** planujemy teraz: bazy produktów / wyszukiwarki „Add Food” z `docs/UI design.md`, powrotu do AI/NLP, soft delete wpisów, frameworka frontendowego, multi-tenant.
