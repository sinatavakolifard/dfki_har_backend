from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://har:har-dev-password@localhost:5432/har",
        alias="DATABASE_URL",
    )
    api_key: str = Field(alias="HAR_API_KEY")
    max_upload_bytes: int = Field(default=50 * 1024 * 1024, alias="HAR_MAX_UPLOAD_BYTES")


@lru_cache
def get_settings() -> Settings:
    return Settings()
