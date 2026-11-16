from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
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
    jwt_expire_min: int = 720
    cors_origins: str = "http://localhost:5173"
    demo_user_email: str | None = None
    demo_user_password: str | None = None
    demo_farm_name: str = "Demo farm"
    demo_farm_lat: Decimal | None = None
    demo_farm_lon: Decimal | None = None
    demo_farm_tz: str = "Africa/Algiers"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_min_length(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
