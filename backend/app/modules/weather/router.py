import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentFarm, Db
from app.core.errors import AppError
from app.modules.weather.client import WeatherProviderError
from app.modules.weather.schemas import (
    DailyOut,
    DegreeDaysOut,
    ForecastOut,
    GddSettingIn,
    GddSettingListItem,
    GddSettingOut,
    NowOut,
    RefreshOut,
    ThresholdsIn,
    ThresholdsOut,
)
from app.modules.weather.service import (
    read_daily,
    read_degree_days,
    read_forecast,
    read_gdd_setting,
    read_gdd_settings,
    read_now,
    read_thresholds,
    refresh,
    write_gdd_setting,
    write_thresholds,
)

router = APIRouter(prefix="/farms/{farm_id}", tags=["weather"])


@router.post("/weather/refresh", response_model=RefreshOut)
def refresh_weather(farm: CurrentFarm, db: Db) -> RefreshOut:
    try:
        return refresh(db, farm)
    except WeatherProviderError:
        raise AppError("weather.provider_unavailable", 502) from None


@router.get("/weather/now", response_model=NowOut)
def weather_now(farm: CurrentFarm, db: Db) -> NowOut:
    return read_now(db, farm)


@router.get("/weather/forecast", response_model=ForecastOut)
def weather_forecast(farm: CurrentFarm, db: Db) -> ForecastOut:
    return read_forecast(db, farm)


@router.get("/weather/daily", response_model=DailyOut)
def weather_daily(
    farm: CurrentFarm,
    db: Db,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> DailyOut:
    return read_daily(db, farm, from_date=from_date, to_date=to_date)


@router.get("/weather/degree-days", response_model=DegreeDaysOut)
def weather_degree_days(
    farm: CurrentFarm,
    db: Db,
    crop_id: uuid.UUID,
    from_date: Annotated[date | None, Query(alias="from")] = None,
) -> DegreeDaysOut:
    return read_degree_days(db, farm, crop_id, from_date)


@router.get("/thresholds", response_model=ThresholdsOut)
def get_thresholds(farm: CurrentFarm, db: Db) -> ThresholdsOut:
    return read_thresholds(db, farm)


@router.put("/thresholds", response_model=ThresholdsOut)
def put_thresholds(body: ThresholdsIn, farm: CurrentFarm, db: Db) -> ThresholdsOut:
    return write_thresholds(db, farm, body)


@router.get("/gdd-settings", response_model=list[GddSettingListItem])
def list_gdd_settings(farm: CurrentFarm, db: Db) -> list[GddSettingListItem]:
    return read_gdd_settings(db, farm)


@router.get("/gdd-settings/{crop_id}", response_model=GddSettingOut)
def get_gdd_setting(crop_id: uuid.UUID, farm: CurrentFarm, db: Db) -> GddSettingOut:
    return read_gdd_setting(db, farm, crop_id)


@router.put("/gdd-settings/{crop_id}", response_model=GddSettingOut)
def put_gdd_setting(
    crop_id: uuid.UUID,
    body: GddSettingIn,
    farm: CurrentFarm,
    db: Db,
) -> GddSettingOut:
    return write_gdd_setting(db, farm, crop_id, body)
