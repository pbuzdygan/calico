from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CALICO API"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_timezone: str = "Europe/Warsaw"
    sqlite_path: str = "/data/calico.db"
    cors_origin: str = ""
    # false = nowe konta tylko gdy nie ma jeszcze zadnego uzytkownika (pierwszy start, D10).
    allow_signup: bool = True
    frontend_dir: str = "/app/frontend"
    # Pusty = sekret generowany automatycznie i zapisany w bazie (app_meta.session_secret).
    session_secret: str = ""
    session_ttl_hours: int = 12

    # extra="ignore": stare klucze w .env (np. ADMIN_PIN, DIAGNOSTICS_PATH, DEFAULT_USER_PIN) nie blokuja startu.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
