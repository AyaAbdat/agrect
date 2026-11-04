from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    cors_origins: str = "http://localhost:5173"
    demo_farm_lat: Decimal | None = None
    demo_farm_lon: Decimal | None = None
    demo_farm_tz: str = "Africa/Algiers"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
