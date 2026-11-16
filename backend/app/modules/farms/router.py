from fastapi import APIRouter

from app.core.deps import CurrentFarm, Db
from app.modules.farms.schemas import FarmOut, WeatherSourceUpdate
from app.modules.farms.service import apply_weather_source, to_farm_out

router = APIRouter(prefix="/farms", tags=["farms"])


@router.get("/{farm_id}", response_model=FarmOut)
def read_farm(farm: CurrentFarm, db: Db) -> FarmOut:
    return to_farm_out(db, farm)


@router.put("/{farm_id}/weather-source", response_model=FarmOut)
def update_weather_source(body: WeatherSourceUpdate, farm: CurrentFarm, db: Db) -> FarmOut:
    apply_weather_source(
        db,
        farm,
        weather_source=body.weather_source,
        lat=body.lat,
        lon=body.lon,
        timezone=body.timezone,
    )
    return to_farm_out(db, farm)
