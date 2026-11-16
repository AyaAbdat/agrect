from datetime import UTC, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.farms.models import Farm, WeatherSource
from app.modules.farms.schemas import FarmOut


def location_point(lon: Decimal, lat: Decimal):
    """WGS84 point. PostGIS ST_MakePoint takes longitude, then latitude."""
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def _clean_coordinate(value: object) -> Decimal | None:
    if value is None:
        return None
    decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    quantized = decimal.quantize(Decimal("0.000001"))
    rendered = format(quantized, "f").rstrip("0").rstrip(".")
    if rendered in {"", "-", "-0"}:
        return Decimal("0")
    return Decimal(rendered)


def read_lat_lon(db: Session, farm: Farm) -> tuple[Decimal | None, Decimal | None]:
    lat, lon = db.execute(
        select(
            cast(func.ST_Y(Farm.location), Numeric(12, 6)),
            cast(func.ST_X(Farm.location), Numeric(12, 6)),
        ).where(Farm.id == farm.id)
    ).one()
    return _clean_coordinate(lat), _clean_coordinate(lon)


def to_farm_out(db: Session, farm: Farm) -> FarmOut:
    lat, lon = read_lat_lon(db, farm)
    return FarmOut(
        id=farm.id,
        name=farm.name,
        lat=lat,
        lon=lon,
        timezone=farm.timezone,
        weather_source=farm.weather_source,
        version=farm.version,
    )


def _timezone_ok(name: str) -> bool:
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return False
    return True


def apply_weather_source(
    db: Session,
    farm: Farm,
    *,
    weather_source: WeatherSource,
    lat: Decimal,
    lon: Decimal,
    timezone: str | None,
) -> None:
    fields: dict[str, str] = {}
    if weather_source == WeatherSource.station:
        fields["weather_source"] = "farm.station_not_supported"
    if lat < Decimal("-90") or lat > Decimal("90"):
        fields["lat"] = "farm.lat_out_of_range"
    if lon < Decimal("-180") or lon > Decimal("180"):
        fields["lon"] = "farm.lon_out_of_range"
    if timezone is not None and not _timezone_ok(timezone):
        fields["timezone"] = "farm.timezone_invalid"
    if fields:
        raise AppError("validation_error", 422, fields)

    farm.location = location_point(lon, lat)
    if timezone is not None:
        farm.timezone = timezone
    farm.weather_source = WeatherSource.service
    farm.version += 1
    farm.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(farm)
