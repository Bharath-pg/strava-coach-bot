from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    llm_provider: str = "groq"
    database_url: str = "postgresql+asyncpg://assistant:assistant@localhost:5432/assistant_db"
    allowed_user_ids: str = ""
    log_level: str = "INFO"

    strava_client_id: str = ""
    strava_client_secret: str = ""
    strava_refresh_token: str = ""

    @property
    def async_database_url(self) -> str:
        """Normalize DATABASE_URL for async SQLAlchemy (Railway uses postgres://)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def allowed_users(self) -> set[int]:
        if not self.allowed_user_ids.strip():
            return set()
        return {int(uid.strip()) for uid in self.allowed_user_ids.split(",") if uid.strip()}

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
