from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./dev.db"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]

    default_timezone: str = "Europe/London"
    default_wpm: int = 150

    llm_provider: str = "fake"
    transcription_provider: str = "fake"
    reminder_provider: str = "console"

    @property
    def is_development(self) -> bool:
        return self.env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
