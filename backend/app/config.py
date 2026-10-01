from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CALICO API"
    app_timezone: str = "Europe/Warsaw"
    sqlite_path: str = "/data/calico.db"
    cors_origin: str = ""
    # false = nowe konta tylko gdy nie ma jeszcze zadnego uzytkownika (pierwszy start, D10).
    allow_signup: bool = True
    frontend_dir: str = "/app/frontend"
    # Pusty = sekret generowany automatycznie i zapisany w bazie (app_meta.session_secret).
    session_secret: str = ""
    session_ttl_hours: int = 12
    # T-PUB: minimalna dlugosc nowego PIN-u (4-8); krotszy PIN istniejacego konta wymusza zmiane po zalogowaniu.
    pin_min_length: int = Field(default=6, ge=4, le=8)
    # T-PUB: false = ekran logowania bez listy uzytkownikow (logowanie nazwa + PIN-em).
    show_user_list: bool = True
    # Interaktywna dokumentacja API (/docs, /redoc, /openapi.json) - domyslnie wylaczona (publiczny obraz).
    api_docs: bool = False
    # Maks. rozmiar tresci zadania; import CSV (1 000 000 znakow) musi sie zmiescic.
    max_request_bytes: int = 4 * 1024 * 1024

    # extra="ignore": stare klucze w .env (np. ADMIN_PIN, DIAGNOSTICS_PATH, DEFAULT_USER_PIN, APP_ENV) nie blokuja startu.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
