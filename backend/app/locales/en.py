"""Angielskie tlumaczenia komunikatow API. Klucz = polski tekst z t("...") (jezyk zrodlowy).

Kompletnosc pilnuje tests/test_i18n.py: kazdy t("...") musi miec wpis, nieuzywane wpisy sa bledem,
parametry {nazwa} musza sie zgadzac.
"""

MESSAGES: dict[str, str] = {
    # etykiety typow wpisow i pol
    "Waga": "Weight",
    "Obwód pasa": "Waist",
    "Śniadanie": "Breakfast",
    "Obiad": "Lunch",
    "Kolacja": "Dinner",
    "Przekąska": "Snack",
    "Bilans dnia": "Daily balance",
    "Ilość kalorii": "Calories",
    "Węglowodany": "Carbs",
    "Tłuszcze": "Fat",
    "Białko": "Protein",
    # CSV
    "Data": "Date",
    "Waga (kg)": "Weight (kg)",
    "Obwód pasa (cm)": "Waist (cm)",
    "Kalorie (kcal)": "Calories (kcal)",
    "Białko (g)": "Protein (g)",
    "Węglowodany (g)": "Carbs (g)",
    "Tłuszcze (g)": "Fat (g)",
    "# Przykład – jeden wiersz na dzień, puste komórki są pomijane. Wiersze zaczynające się od # są ignorowane.": (
        "# Example – one row per day, empty cells are skipped. Rows starting with # are ignored."
    ),
    "calico-szablon-importu.csv": "calico-import-template.csv",
    "Plik jest pusty.": "The file is empty.",
    "Brak kolumny „Data”. Pobierz szablon z aplikacji.": "Missing “Date” column. Download the template from the app.",
    "Brak daty.": "Missing date.",
    "Podano makroskładniki bez kalorii – uzupełnij kolumnę „Kalorie”.": "Macros given without calories – fill in the “Calories” column.",
    "Nieznana kolumna „{name}”. Dozwolone kolumny: {expected}. Pobierz szablon z aplikacji.": (
        "Unknown column “{name}”. Allowed columns: {expected}. Download the template from the app."
    ),
    "Kolumna „{name}” występuje w pliku więcej niż raz.": "Column “{name}” appears more than once in the file.",
    "Za dużo wierszy ({count}). Maksymalnie {max} w jednym pliku.": "Too many rows ({count}). At most {max} per file.",
    "Dzień {date} występuje w pliku więcej niż raz (wiersz {row}).": "Day {date} appears more than once in the file (row {row}).",
    # walidacja i parser
    "Niepoprawna wartość pola '{field}': '{value}'. Podaj liczbę nieujemną, np. {example}.": (
        "Invalid value for '{field}': '{value}'. Enter a non-negative number, e.g. {example}."
    ),
    "Niepoprawny format daty. Użyj RRRR-MM-DD, DD.MM.RRRR, DD-MM-RRRR albo DD/MM/RRRR.": (
        "Invalid date format. Use YYYY-MM-DD, DD.MM.YYYY, DD-MM-YYYY or DD/MM/YYYY."
    ),
    "Niepoprawny format miesiąca. Użyj RRRR-MM.": "Invalid month format. Use YYYY-MM.",
    "Brak treści wpisu. Użyj jednego z gotowych szablonów.": "The entry is empty. Use one of the templates.",
    "Nie rozpoznano typu wpisu. Użyj jednego z nagłówków: {headers}.": "Unknown entry type. Use one of these headers: {headers}.",
    "Podaj wartość w formacie '{example}'.": "Enter the value as '{example}'.",
    "Nieoczekiwana linia we wpisie '{label}': '{line}'.": "Unexpected line in the '{label}' entry: '{line}'.",
    "Nagłówek '{label}' zapisz w osobnej linii, a wartości w kolejnych liniach:\n\n{example}": (
        "Put the '{label}' header on its own line and the values on the following lines:\n\n{example}"
    ),
    "Niepoprawna linia: '{line}'. Każda wartość musi mieć format 'Pole: liczba'.": "Invalid line: '{line}'. Each value must be written as 'Field: number'.",
    "Nieznane pole '{field}'. Użyj: {fields}.": "Unknown field '{field}'. Use: {fields}.",
    "Pole '{field}' podano więcej niż raz.": "Field '{field}' was given more than once.",
    "Brak wartości dla pola '{field}'.": "Missing value for '{field}'.",
    "Brakuje pól: {fields}. Wzór:\n\n{example}": "Missing fields: {fields}. Template:\n\n{example}",
    "Brakuje pól: {fields}.": "Missing fields: {fields}.",
    "Data {date} jest zbyt odległa. Najwcześniejsza dozwolona data to {earliest}.": "Date {date} is too far back. The earliest allowed date is {earliest}.",
    "Data {date} jest z przyszłości. Najpóźniejsza dozwolona data to {latest}.": "Date {date} is in the future. The latest allowed date is {latest}.",
    "Wartość pola '{field}' ({value} {unit}) jest poza zakresem {low}-{high} {unit}.": "The value of '{field}' ({value} {unit}) is outside the range {low}-{high} {unit}.",
    "W dniu {date} jest już wpis '{label}'. Edytuj go zamiast tworzyć drugi.": "There is already a '{label}' entry on {date}. Edit it instead of creating another one.",
    "Nie znaleziono pozycji.": "Entry not found.",
    "Zakres raportu może mieć najwyżej {days} dni.": "A report range can be at most {days} days.",
    "Podaj 'entry' albo 'source_text'.": "Provide 'entry' or 'source_text'.",
    "Brak wpisów do cofnięcia w tym dniu.": "There are no entries to undo on this day.",
    # konto i uwierzytelnianie
    "Za dużo błędnych prób PIN-u. Spróbuj ponownie za {minutes} min.": "Too many wrong PIN attempts. Try again in {minutes} min.",
    "Niepoprawny PIN.": "Wrong PIN.",
    "Niepoprawny PIN. Pozostałe próby: {left}.": "Wrong PIN. Attempts left: {left}.",
    "Sesja wygasła albo PIN jest niepoprawny – odblokuj ponownie.": "Your session has expired or the PIN is wrong – unlock again.",
    "Uzupełnij profil (płeć, wiek, wzrost, waga, aktywność, cel) – bez niego CALICO nie może wyliczyć planu.": (
        "Complete your profile (sex, age, height, weight, activity, goal) – CALICO cannot calculate a plan without it."
    ),
    "Zakładanie nowych kont jest wyłączone (ALLOW_SIGNUP=false).": "Creating new accounts is disabled (ALLOW_SIGNUP=false).",
    "PIN musi mieć 4-8 cyfr.": "The PIN must have 4-8 digits.",
    "Start planu nie może być w przyszłości.": "The plan start cannot be in the future.",
    "Start planu nie może być wcześniejszy niż {date}.": "The plan start cannot be earlier than {date}.",
    # czat / tryb tekstowy
    "W {carbs} g · T {fat} g · B {protein} g": "C {carbs} g · F {fat} g · P {protein} g",
    "Suma: {total} kcal / cel {target} kcal | {macros}.": "Total: {total} kcal / target {target} kcal | {macros}.",
    "Brak wpisów w dniu {date}. {summary}": "No entries on {date}. {summary}",
    "Pozycje dnia {date}:": "Entries for {date}:",
    "Aktywny jest Bilans dnia – zastępuje sumę posiłków.": "A daily balance is active – it replaces the sum of meals.",
    "W tym dniu jest Bilans dnia – zastępuje sumę posiłków.": "This day has a daily balance – it replaces the sum of meals.",
    "Używaj gotowych szablonów. Typy wpisów: {types}. Opcjonalnie dodaj pierwszą linię 'Data: RRRR-MM-DD'.\n\n"
    "Komendy: 'pokaż dziś', 'cofnij ostatni', 'usuń 2'.\n\nPrzykład:\nData: 2026-08-03\n{example}": (
        "Use the templates. Entry types: {types}. Optionally add a first line 'Date: YYYY-MM-DD'.\n\n"
        "Commands: 'show today', 'undo', 'delete 2'.\n\nExample:\nDate: 2026-08-03\n{example}"
    ),
    "Brak dzisiejszych wpisów do cofnięcia.": "There are no entries to undo today.",
    "Cofnąłem wpis: {entry}.": "Undid entry: {entry}.",
    "Nie znalazłem dzisiejszej pozycji nr {position}. Wpisz 'pokaż dziś', aby zobaczyć numerację.": (
        "Today's entry no. {position} was not found. Type 'show today' to see the numbering."
    ),
    "Usunąłem pozycję nr {position}: {entry}.": "Deleted entry no. {position}: {entry}.",
    "Zapisałem wagę dla dnia {date}: {value} kg. Cel kcal nie zmienia się automatycznie – ocenę planu znajdziesz w zakładce Cele.": (
        "Saved weight for {date}: {value} kg. The calorie target does not change automatically – see the plan review in Goals."
    ),
    "Zaktualizowałem wagę dla dnia {date}: {value} kg. Cel kcal nie zmienia się automatycznie – ocenę planu znajdziesz w zakładce Cele.": (
        "Updated weight for {date}: {value} kg. The calorie target does not change automatically – see the plan review in Goals."
    ),
    "Zapisałem obwód pasa dla dnia {date}: {value} cm.": "Saved waist for {date}: {value} cm.",
    "Zaktualizowałem obwód pasa dla dnia {date}: {value} cm.": "Updated waist for {date}: {value} cm.",
    "Zapisałem wpis ({date}): {entry}": "Saved entry ({date}): {entry}",
    "Zaktualizowałem wpis ({date}): {entry}": "Updated entry ({date}): {entry}",
    # ocena planu i prognoza
    "Nie znaleziono profilu.": "Profile not found.",
    "Brak aktualnej sugestii zmiany celu.": "There is no current target suggestion.",
    "Sugestia zmieniła się w międzyczasie. Odśwież ocenę planu.": "The suggestion has changed in the meantime. Refresh the plan review.",
    "Brak pomiarów wagi. Dodawaj wpis „Waga” regularnie (np. 2–3 razy w tygodniu, rano, na czczo).": (
        "No weight measurements. Log your weight regularly (e.g. 2–3 times a week, in the morning, before eating)."
    ),
    "Za mało danych do oceny trendu: potrzeba co najmniej {needed} pomiarów z {span_needed} dni od startu planu "
    "(jest {count} z {span} dni). Cel pozostaje bez zmian.": (
        "Not enough data to assess the trend: at least {needed} measurements over {span_needed} days since the plan start are needed "
        "(there are {count} over {span} days). The target stays the same."
    ),
    "Wpisy jedzenia pokrywają {coverage}% dni okresu – za mało (min. {minimum}), by oszacować rzeczywiste zapotrzebowanie z obserwacji.": (
        "Food entries cover {coverage}% of the days in the period – too few (min. {minimum}) to estimate your actual needs from observation."
    ),
    "Plan działa: tempo {rate} mieści się w zakresie {low} … {high} Cel pozostaje: {target} kcal.": (
        "The plan is working: a rate of {rate} is within {low} … {high} The target stays at {target} kcal."
    ),
    "Plan trwa dopiero {days} dni – poczekaj do {minimum} dni przed korektą.": "The plan has only been running for {days} days – wait until {minimum} days before adjusting.",
    "Obecny cel ({target} kcal) jest już na dolnej granicy ({floor} kcal) – dalsze obniżanie wymaga konsultacji ze specjalistą.": (
        "The current target ({target} kcal) is already at the lower limit ({floor} kcal) – lowering it further requires consulting a specialist."
    ),
    "Sugerowane zwiększenie celu do {suggested} kcal ({delta} kcal).": "Suggested increase of the target to {suggested} kcal ({delta} kcal).",
    "Sugerowane zmniejszenie celu do {suggested} kcal ({delta} kcal).": "Suggested decrease of the target to {suggested} kcal ({delta} kcal).",
    "Szacowane zapotrzebowanie (wzór, średnia masa {weight} kg) spadło do {tdee} kcal (start planu: {plan_tdee} kcal). "
    "To samo w sobie nie zmienia celu – decyduje faktyczny trend masy.": (
        "Estimated needs (formula, average weight {weight} kg) dropped to {tdee} kcal (plan start: {plan_tdee} kcal). "
        "This alone does not change the target – the actual weight trend decides."
    ),
    "Szacowane zapotrzebowanie (wzór, średnia masa {weight} kg) wzrosło do {tdee} kcal (start planu: {plan_tdee} kcal). "
    "To samo w sobie nie zmienia celu – decyduje faktyczny trend masy.": (
        "Estimated needs (formula, average weight {weight} kg) rose to {tdee} kcal (plan start: {plan_tdee} kcal). "
        "This alone does not change the target – the actual weight trend decides."
    ),
    "{value} kg/tydz.": "{value} kg/wk",
    "(oczekiwane {low} … {high})": "(expected {low} … {high})",
    "Masa spada za szybko: {rate} {band}.": "Weight is dropping too fast: {rate} {band}.",
    "Redukcja zwolniła: {rate} {band}.": "Weight loss has slowed down: {rate} {band}.",
    "Przyrost masy jest za wolny: {rate} {band}.": "Weight gain is too slow: {rate} {band}.",
    "Masa rośnie za szybko: {rate} {band}.": "Weight is rising too fast: {rate} {band}.",
    "Masa spada: {rate} {band}.": "Weight is dropping: {rate} {band}.",
    "Masa rośnie: {rate} {band}.": "Weight is rising: {rate} {band}.",
    "Waga docelowa {target} kg osiągnięta.": "Target weight of {target} kg reached.",
    "przy obecnym trendzie ({rate})": "at the current trend ({rate})",
    "według tempa planu ({rate}; za mało pomiarów do trendu)": "at the planned rate ({rate}; not enough measurements for a trend)",
    "Obecny trend ({rate}) nie prowadzi do wagi docelowej {target} kg.": "The current trend ({rate}) does not lead to the target weight of {target} kg.",
    "Plan nie zakłada zmiany masy w kierunku wagi docelowej {target} kg.": "The plan does not expect weight to move towards the target of {target} kg.",
    "Waga docelowa {target} kg za ponad 3 lata – {source}.": "Target weight of {target} kg in more than 3 years – {source}.",
    "Waga docelowa {target} kg około {date} (za ok. {weeks} tyg.) – {source}.": "Target weight of {target} kg around {date} (in about {weeks} wk) – {source}.",
}
