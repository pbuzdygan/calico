# CALICO

CALICO to prosty dziennik kalorii i makroskladnikow z interfejsem czatowym opartym o szablony wiadomosci. Aplikacja nie korzysta juz z AI ani parsera jezyka naturalnego.

## Co robi aplikacja

- prowadzi wpisy dzienne per user
- zapisuje:
  - `Waga`
  - `Obwod pasa`
  - `Sniadanie`
  - `Obiad`
  - `Kolacja`
  - `Przekaska`
  - `Bilans dnia`
- liczy sume kcal i makr dla dnia
- obsluguje raporty 5/7/30 dni oraz zakres i miesiac
- ma PIN per user
- ma tryb diagnostyczny `Admin`

## Najwazniejsze reguly

- jesli nie podasz `Data:`, wpis trafia do dnia biezacego
- akceptowane formaty dat:
  - `YYYY-MM-DD`
  - `DD.MM.YYYY`
  - `DD-MM-YYYY`
  - `DD/MM/YYYY`
- `Waga` i `Obwod pasa`: jeden aktywny wpis na dzien, nowy wpis nadpisuje poprzedni
- `Sniadanie`, `Obiad`, `Kolacja`, `Przekaska`: mozna dodawac wiele wpisow jednego dnia
- kolejne wpisy tego samego typu dostaja etykiety typu:
  - `Sniadanie`
  - `Sniadanie Drugie`
  - `Sniadanie Trzecie`
- `Bilans dnia` jest jeden na dzien i zastępuje sume wszystkich posilkow z tego dnia

## Szablony wiadomosci

Waga:

```text
Waga:
Waga: 82.4 kg
```

Obwod pasa:

```text
Obwod pasa:
Obwod pasa: 91 cm
```

Sniadanie / Obiad / Kolacja / Przekaska:

```text
Sniadanie
Ilosc kalorii: 540
Weglowodany: 48
Tluszcze: 18
Bialko: 32
```

Bilans dnia:

```text
Bilans dnia
Ilosc kalorii: 2150
Weglowodany: 210
Tluszcze: 70
Bialko: 145
```

Z data:

```text
Data: 2026-08-03
Kolacja
Ilosc kalorii: 610
Weglowodany: 40
Tluszcze: 22
Bialko: 38
```

## Start

1. Skopiuj konfiguracje:

```bash
cp .env.example .env
```

2. Uruchom:

```bash
docker compose up --build -d
```

3. Otworz:

```text
http://localhost:8080
```

4. Przy pierwszym starcie:

- domyslny user: `Domyslny Uzytkownik`
- domyslny PIN: z `DEFAULT_USER_PIN` (domyslnie `1234`)

## UI

Glowne sekcje:

- `Czat`
- `Dziennik`
- `Raporty`
- `Uzytkownik`
- `Admin`

W czacie sa gotowe przyciski szablonow. Klikniecie wstawia wzor do edycji. Nie trzeba wpisywac komend naturalnym jezykiem.

## Dziennik i raporty

API:

- `GET /api/days/current?user_id=`
- `GET /api/days?user_id=&limit=`
- `GET /api/days/{log_date}?user_id=`
- `PATCH /api/days/{log_date}/entries/{entry_id}?user_id=`
- `DELETE /api/days/{log_date}/entries/{entry_id}?user_id=`
- `POST /api/days/{log_date}/clear?user_id=`
- `POST /api/days/{log_date}/close?user_id=`
- `POST /api/days/{log_date}/reopen?user_id=`

Raporty:

- `GET /api/reports/summary?user_id=&days=7`
- `GET /api/reports/range?user_id=&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`
- `GET /api/reports/month?user_id=&month=YYYY-MM`

## PIN auth

- kazdy user ma osobny PIN 4-8 cyfr
- PIN jest haszowany po stronie backendu
- po wpisaniu PIN-u mozna nacisnac `Enter`
- user moze usunac swoje konto z sekcji `Uzytkownik`

## Profil i cel kcal

Profil sluzy do wyliczenia celu kcal wzorem Mifflin-St Jeor z aktywnoscia i celem:

- `maintain`: 0%
- `cut`: zwykle 10-20%
- `bulk`: zwykle 5-15%

Wpisy `Waga` z czatu sa historia pomiarow dnia. Profil nadal ma osobna wartosc `Waga kg` do celu kalorycznego.

## Diagnostyka i Admin

- jesli ustawisz `ADMIN_PIN` w `.env`, aplikacja wlacza tryb `Admin`
- kazda interakcja z czatem zapisuje sie do JSONL per user w `DIAGNOSTICS_PATH`
- przy usunieciu usera usuwane sa jego logi diagnostyczne

## Security baseline

- brak kluczy AI i brak integracji z zewnetrznym LLM
- SQLite w trybie `WAL`
- `busy_timeout`
- `foreign_keys=ON`
- sekrety poza repo (`.env` w `.gitignore`)

## Troubleshooting

Po zmianach backendu i frontendu wykonaj pelny restart:

```bash
docker compose down
docker compose up --build -d
```

Jesli frontend nie odpowiada poprawnie:

```bash
docker compose logs proxy --tail=100
docker compose logs backend --tail=100
docker compose ps
```
