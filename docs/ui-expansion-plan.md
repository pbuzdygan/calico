# CALICO: plan rozbudowy `Dziennik` + `Raporty` + odswiezenie UI

## Cel

Rozszerzyc obecne MVP o dwie brakujace warstwy:

- `Dziennik`, czyli kontrolowany widok do zarzadzania wpisami i czyszczenia danych
- `Raporty`, czyli widok zakresow czasu, trendow i porownania do celu

Rownolegle przebudowac frontend tak, aby:

- chat zostal glownym miejscem szybkiego dodawania
- operacje administracyjne byly wykonywane w zwyklym UI, nie przez wymuszone komendy tekstowe
- interfejs byl bardziej wyrazisty, mniej "piaskowy" i lepiej dzialal na waskich ekranach

## Docelowa architektura UI

Nowa nawigacja aplikacji:

- `Czat`
- `Dziennik`
- `Raporty`
- `Uzytkownik`

### 1. `Czat`

Zakres:

- szybkie dodawanie wpisow
- szybkie pytania typu `pokaz dzis`, `podsumuj dzien`
- szybkie cofniecie ostatniej operacji

Widok:

- kompaktowy naglowek z aktywnym userem i bilansem dnia
- historia rozmowy
- szybkie akcje
- po prawej lub pod spodem mini-panel "Dzisiaj"

### 2. `Dziennik`

Zakres:

- lista dni
- lista pozycji dla wybranego dnia
- operacje na pozycjach bez wpisywania komend

Funkcje:

- wybierz dzien z kalendarza lub z listy ostatnich dni
- zobacz wszystkie pozycje z kcal
- `edytuj`
- `usun`
- `duplikuj`
- `przenies do innego dnia`
- `wyczysc dzien`
- `otworz ponownie`
- `podsumuj dzien`

### 3. `Raporty`

Zakres:

- gotowe zakresy czasu:
  - ostatnie 5 dni
  - ostatnie 7 dni
  - ostatnie 30 dni
  - ten miesiac
  - zakres `od-do`
- wykres dziennych kcal
- linia celu kcal
- srednia kcal
- liczba dni z wpisami
- liczba dni powyzej / ponizej celu

MVP raportow:

- karta podsumowania
- prosty wykres slupkowy lub liniowy
- tabela ostatnich dni

### 4. `Uzytkownik`

Zakres:

- profil
- PIN
- cel kcal
- ustawienia parsera i preferencje

To odciaza chat i sidebar. Profil nie powinien dominowac na ekranie glownym.

## Zarzadzanie czystoscia danych

Chat nie powinien byc jedynym narzedziem do utrzymania porzadku. Dlatego `Dziennik` jest warstwa kontrolna.

### Operacje dzienne

- `Podsumuj dzien`
- `Otworz ponownie`
- `Wyczysc dzien`
- `Usun wszystkie pozycje 0 kcal`
- `Pokaz tylko poprawne wpisy`

### Operacje na pozycji

- `Edytuj`
- `Usun`
- `Duplikuj`
- `Przenies`
- `Oznacz jako testowy / bledny`

## Zmiany backendowe

## Etap 1: endpointy dziennika

Dodac:

- `GET /api/days?user_id=&limit=`
- `GET /api/days/{log_date}?user_id=`
- `DELETE /api/days/{log_date}/meals/{meal_id}`
- `PATCH /api/days/{log_date}/meals/{meal_id}`
- `POST /api/days/{log_date}/meals/{meal_id}/duplicate`
- `POST /api/days/{log_date}/meals/{meal_id}/move`
- `POST /api/days/{log_date}/clear`
- `POST /api/days/{log_date}/reopen`

Wymaganie:

- po kazdej operacji musi zostac przeliczona `day_log.total_kcal`

## Etap 2: raporty

Dodac:

- `GET /api/reports/summary?user_id=&days=7`
- `GET /api/reports/range?user_id=&date_from=&date_to=`
- `GET /api/reports/month?user_id=&month=YYYY-MM`

Zwracane dane:

- lista dni
- total kcal per day
- target kcal per day
- average kcal
- delta do celu

## Etap 3: model danych

Na MVP mozna zostac przy obecnym modelu i twardym usuwaniu, ale kod warto przygotowac na przyszly `soft delete`.

Rekomendowane rozszerzenia:

- `Meal.deleted_at`
- `Meal.is_deleted`
- opcjonalnie `Meal.is_flagged`

Nie trzeba tego wdrazac od razu, ale warto zaprojektowac API tak, aby przejscie bylo proste.

## Zmiany frontendowe

## Faza A: nowy layout

- zastapic staly sidebar ukladem:
  - gorna belka
  - zakladki
  - glowny obszar tresci
- profil przeniesc do osobnej sekcji
- karta "Dzisiaj" powinna byc kompaktowa i zawsze widoczna

## Faza B: dziennik

- lista dni po lewej lub jako filtr nad tabela
- lista pozycji dnia jako tabela/karty
- akcje per rekord
- przycisk `wyczysc dzien`

## Faza C: raporty

- gotowe filtry zakresow
- wykres
- tabela dni
- karta "srednia vs cel"

## Strategia wdrozenia

### Sprint 1

- nowy layout aplikacji
- nawigacja `Czat / Dziennik / Raporty / Uzytkownik`
- przeniesienie formularza profilu do `Uzytkownik`
- kompaktowa karta dnia

### Sprint 2

- endpointy i UI dla `Dziennik`
- edycja / usuwanie / czyszczenie dnia
- poprawne przeliczanie sum po kazdej operacji

### Sprint 3

- endpointy i UI dla `Raporty`
- ostatnie 5 / 7 / 30 dni
- miesiac
- wykres

### Sprint 4

- dopracowanie ergonomii:
  - filtrowanie
  - oznaczanie wpisow problematycznych
  - lepsze komunikaty przy pozycjach 0 kcal

## Wybrany kierunek UI

Wybrany kierunek wdrozenia nie bedzie kopia jednego mockupu 1:1.
Docelowy interfejs laczy trzy najmocniejsze cechy przygotowanych wariantow:

- z `Operator`:
  - glowny uklad pracy
  - czytelne karty
  - mocna hierarchia sekcji
  - praktyczny charakter widoku `Dziennik`
- z `Pulse`:
  - energia kolorystyczna
  - karta dnia jako centralny element orientacyjny
  - bardziej produktowy charakter raportow
- z `Editorial`:
  - spokojniejsze spacingi
  - czystsza typografia
  - bardziej premium rytm tresci

### Zasady wizualne

- brak "piaskowego" tonu jako dominujacej bazy
- glowna paleta:
  - ciemny granat / petrol jako kolor strukturalny
  - zlany jasny kolor tla dla kart i powierzchni roboczych
  - jeden cieply akcent do CTA i sygnalow kalorii
  - jeden chlodny akcent do raportow i statusow
- typografia:
  - mocny font naglowkowy
  - neutralny, czytelny font tekstowy
- styl:
  - aplikacja ma wygladac jak dopracowane narzedzie, nie jak surowe MVP
  - mniej paneli "jeden pod drugim", wiecej sensownego grupowania i rytmu

### Docelowy shell aplikacji

Widok globalny:

- gorna belka:
  - marka
  - przelacznik sekcji
  - aktywny user
  - stan odblokowania PIN
- glowny obszar:
  - lewa / glowna kolumna dla aktywnej sekcji
  - prawa kolumna dla stalej `Karty dnia`

`Karta dnia` ma byc widoczna prawie zawsze i zawierac:

- suma dnia
- cel dnia
- roznica do celu
- liczbe wpisow
- status dnia
- szybkie akcje:
  - `Pokaz dzis`
  - `Podsumuj dzien`
  - `Wyczysc dzien`
  - `Cofnij ostatni`

## Docelowa kolejnosc wdrozenia

1. nowy shell aplikacji
2. `Czat`
3. `Dziennik`
4. `Raporty`
5. `Uzytkownik`

## Szczegolowy plan wdrozenia

### Faza 0: porzadkowanie kontraktow i danych

Cel:

- ustalic backendowe kontrakty pod nowy frontend, zanim zacznie sie przebudowa widokow

Zakres:

- przeglad obecnych endpointow
- dopisanie brakujacych endpointow dla `Dziennik`
- dopisanie endpointow raportowych
- ustalenie jednego formatu odpowiedzi dla:
  - listy dni
  - listy pozycji dnia
  - raportow zakresowych
- doprecyzowanie zasad przeliczania `day_log.total_kcal` po:
  - dodaniu
  - edycji
  - usunieciu
  - wyczyszczeniu dnia
  - przeniesieniu pozycji

Rezultat:

- frontend nie musi skladac stanu z przypadkowych odpowiedzi chatowych

### Faza 1: nowy shell i design system

Cel:

- zastapic obecny statyczny layout nowa struktura produktu

Zakres:

- nowa gorna belka
- zakladki `Czat / Dziennik / Raporty / Uzytkownik`
- nowa siatka strony
- stale widoczna `Karta dnia`
- tokeny wizualne:
  - kolory
  - radiusy
  - spacing
  - przyciski
  - karty
  - badge
  - puste stany

Rezultat:

- obecny chat zostaje osadzony w nowym shellu bez zmiany logiki backendowej

### Faza 2: sekcja `Czat`

Cel:

- utrzymac szybkie wpisywanie, ale w bardziej uporzadkowanym i dojrzalszym interfejsie

Zakres:

- historia rozmowy w lepszym ukladzie
- sekcja szybkich akcji
- lepsza prezentacja odpowiedzi:
  - wynik posilku
  - skladniki
  - warningi
- mini-podglad ostatnich pozycji dnia obok czatu lub pod nim

Rezultat:

- chat staje sie modułem produktu, a nie jedynym ekranem

### Faza 3: sekcja `Dziennik`

Cel:

- przeniesc realne zarzadzanie wpisami z komend tekstowych do UI

Zakres backend:

- `GET /api/days?user_id=&limit=`
- `GET /api/days/{log_date}?user_id=`
- `PATCH /api/days/{log_date}/meals/{meal_id}`
- `DELETE /api/days/{log_date}/meals/{meal_id}`
- `POST /api/days/{log_date}/meals/{meal_id}/duplicate`
- `POST /api/days/{log_date}/meals/{meal_id}/move`
- `POST /api/days/{log_date}/clear`
- `POST /api/days/{log_date}/remove-zero-kcal`

Zakres frontend:

- lista dni
- filtr dat
- lista pozycji dnia
- akcje na rekordzie:
  - `Edytuj`
  - `Usun`
  - `Duplikuj`
  - `Przenies`
- akcje dla dnia:
  - `Wyczysc dzien`
  - `Usun pozycje 0 kcal`
  - `Podsumuj dzien`
  - `Otworz ponownie`

Rezultat:

- utrzymanie czystosci danych nie wymaga pamietania o konkretnych komendach

### Faza 4: sekcja `Raporty`

Cel:

- pokazac realna wartosc danych historycznych

Zakres backend:

- `GET /api/reports/summary?user_id=&days=7`
- `GET /api/reports/range?user_id=&date_from=&date_to=`
- `GET /api/reports/month?user_id=&month=YYYY-MM`

Zakres frontend:

- gotowe filtry:
  - `5 dni`
  - `7 dni`
  - `30 dni`
  - `miesiac`
  - `zakres`
- karta metryk:
  - srednia kcal
  - najwyzszy dzien
  - liczba dni z wpisami
  - bilans vs cel
- wykres dzienny
- tabela dni z mozliwoscia przejscia do `Dziennik`

Rezultat:

- CALICO przestaje byc tylko licznikiem "na teraz", a staje sie narzedziem do obserwacji trendu

### Faza 5: sekcja `Uzytkownik`

Cel:

- usunac profil z glownego widoku i zrobic dla niego dedykowane miejsce

Zakres:

- profil
- PIN
- cel i aktywnosc
- podglad aktualnych ustawien celu
- opcjonalnie ustawienia parsera / preferencji

Rezultat:

- glowny ekran nie jest zagracony formularzem

### Faza 6: ergonomia i utwardzenie

Cel:

- dopracowac detale, ktore beda widoczne dopiero po pierwszym pelnym przebiegu

Zakres:

- puste stany
- loading states
- komunikaty bledow
- bardziej przewidywalne komunikaty po edycji i usunieciu
- czytelne oznaczenie wpisow problematycznych
- porzadek mobilny i waskie okna

## Techniczna kolejnosc realizacji

### Backend najpierw

1. endpointy `Dziennik`
2. endpointy `Raporty`
3. testy przeliczania sum
4. testy operacji na dniu i pozycjach

### Frontend potem

1. shell aplikacji
2. `Karta dnia`
3. `Czat`
4. `Dziennik`
5. `Raporty`
6. `Uzytkownik`

### Dlaczego w tej kolejnosci

- bez endpointow nowy frontend bedzie sztucznie ograniczony
- `Dziennik` rozwiazuje najwiekszy problem operacyjny: czystosc danych
- `Raporty` powinny wejsc dopiero wtedy, gdy dane sa wygodnie korygowalne

## Priorytety produktowe

### P1

- poprawne przeliczanie dnia po kazdej operacji
- `Dziennik`
- nowy shell UI
- `Karta dnia`

### P2

- raport 7 dni i 30 dni
- czyszczenie dnia
- usuwanie wpisow 0 kcal

### P3

- przenoszenie pozycji miedzy dniami
- bardziej zaawansowane filtry
- miesieczny widok trendu

## Kryteria akceptacji

- user moze utrzymac porzadek bez wpisywania specjalnych komend
- po usunieciu i edycji suma dnia zawsze jest przeliczona
- raport tygodniowy i miesieczny sa dostepne z UI
- interfejs dziala dobrze na desktopie i przy waskim oknie
- wyglad nie przypomina surowego MVP i ma wyrazny kierunek wizualny
