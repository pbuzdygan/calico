from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CALICO API"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_timezone: str = "Europe/Warsaw"
    sqlite_path: str = "/data/calico.db"
    cors_origin: str = ""
    default_user_pin: str = "1234"
    admin_pin: str = ""
    diagnostics_path: str = "/data/diagnostics"
    frontend_dir: str = "/app/frontend"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
