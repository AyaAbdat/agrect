import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field

from app.modules.farms.models import WeatherSource


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool) or not isinstance(value, int | str | float):
        raise ValueError("invalid decimal")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc


Coordinate = Annotated[
    Decimal,
    BeforeValidator(_to_decimal),
    Field(max_digits=12, decimal_places=6, allow_inf_nan=False),
]


class WeatherSourceUpdate(BaseModel):
    weather_source: WeatherSource
    lat: Coordinate
    lon: Coordinate
    timezone: str | None = None


class FarmOut(BaseModel):
    id: uuid.UUID
    name: str
    lat: Coordinate | None
    lon: Coordinate | None
    timezone: str
    weather_source: WeatherSource
    version: int
