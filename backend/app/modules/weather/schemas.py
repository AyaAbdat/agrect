import enum
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_serializer

from app.modules.catalog.schemas import LocalizedName
from app.modules.weather.models import GddMethod


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, bool) or not isinstance(value, int | str | float):
        raise ValueError("invalid decimal")
    else:
        try:
            parsed = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("invalid decimal") from exc
    if not parsed.is_finite():
        raise ValueError("invalid decimal")
    return parsed


def _parse_optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return _parse_decimal(value)


DecimalIn = Annotated[Decimal, BeforeValidator(_parse_decimal)]
OptionalDecimalIn = Annotated[Decimal | None, BeforeValidator(_parse_optional_decimal)]


class ApiModel(BaseModel):
    @field_serializer("*", mode="plain")
    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, enum.Enum):
            return value.value
        return value


class RefreshOut(ApiModel):
    issued_at: datetime
    hours: int
    days: int


class NowOut(ApiModel):
    temp_c: Decimal | None
    rh_pct: Decimal | None
    wind_ms: Decimal | None
    gust_ms: Decimal | None
    wind_dir_deg: Decimal | None
    rad_wm2: Decimal | None
    dewpoint_c: Decimal | None
    vpd_kpa: Decimal | None
    rain_mm: Decimal | None
    et0_mm: Decimal | None
    ts: datetime
    rad_sum_jcm2_today: Decimal | None = None
    issued_at: datetime | None
    stale: bool
    provider: Literal["Open-Meteo"] = "Open-Meteo"
    source: Literal["estimated"] = "estimated"
    dewpoint_source: Literal["calculated"] = "calculated"
    vpd_source: Literal["calculated"] = "calculated"
    rad_sum_source: Literal["calculated"] = "calculated"


class ForecastHourOut(ApiModel):
    ts: datetime
    temp_c: Decimal | None
    rh_pct: Decimal | None
    rain_mm: Decimal | None
    rain_prob_pct: Decimal | None
    wind_ms: Decimal | None
    gust_ms: Decimal | None
    wind_dir_deg: Decimal | None
    rad_wm2: Decimal | None
    et0_mm: Decimal | None
    dewpoint_c: Decimal | None
    vpd_kpa: Decimal | None
    is_forecast: bool
    source: str


class ForecastDayOut(ApiModel):
    date: date
    tmin_c: Decimal | None
    tmax_c: Decimal | None
    rain_mm: Decimal | None
    rain_prob_pct: Decimal | None
    et0_mm: Decimal | None
    frost_h: int | None
    heat_h: int | None
    is_forecast: bool
    source: str


class ForecastOut(ApiModel):
    issued_at: datetime | None
    stale: bool
    hourly: list[ForecastHourOut]
    daily: list[ForecastDayOut]


class DailyRowOut(ApiModel):
    date: date
    tmin_c: Decimal | None
    tmax_c: Decimal | None
    tmean_c: Decimal | None
    rh_min: Decimal | None
    rh_max: Decimal | None
    rain_mm: Decimal | None
    et0_mm: Decimal | None
    vpd_max_kpa: Decimal | None
    frost_h: int | None
    heat_h: int | None
    chill_h: int | None
    hours_count: int
    is_forecast: bool
    source: str


class DailyOut(ApiModel):
    issued_at: datetime | None
    stale: bool
    days: list[DailyRowOut]


class ThresholdsIn(BaseModel):
    frost_c: OptionalDecimalIn = None
    heat_c: OptionalDecimalIn = None
    vpd_limit_kpa: OptionalDecimalIn = None
    chill_season_start: date | None = None


class ThresholdsOut(ApiModel):
    frost_c: Decimal | None
    heat_c: Decimal | None
    vpd_limit_kpa: Decimal | None
    chill_season_start: date | None


class GddSettingIn(BaseModel):
    base_c: DecimalIn
    upper_c: OptionalDecimalIn = None
    method: GddMethod
    start_date: date | None = None


class GddSettingOut(ApiModel):
    crop_id: uuid.UUID
    base_c: Decimal | None
    upper_c: Decimal | None
    method: GddMethod | None
    start_date: date | None = None


class BlockGddSettingOut(ApiModel):
    block_id: uuid.UUID
    base_c: Decimal | None
    upper_c: Decimal | None
    method: GddMethod | None
    start_date: date | None = None
    version: int | None = None


class GddSettingListItem(ApiModel):
    crop_id: uuid.UUID
    code: str
    name: LocalizedName
    base_c: Decimal
    upper_c: Decimal | None
    method: GddMethod
    start_date: date | None


class GddSettingBrief(ApiModel):
    base_c: Decimal
    upper_c: Decimal | None
    method: GddMethod
    start_date: date | None = None
    override: bool = False


class DegreeDayPoint(ApiModel):
    date: date
    gdd: Decimal | None
    gdd_cum: Decimal | None
    is_forecast: bool


class ChillOut(ApiModel):
    season_start: date | None
    hours_total: int | None


class DegreeDaysOut(ApiModel):
    model_config = ConfigDict(populate_by_name=True)

    setting: GddSettingBrief | None
    from_date: date = Field(alias="from")
    data_from: date | None
    days: list[DegreeDayPoint]
    gdd_total: Decimal | None
    chill: ChillOut
    frost_h_total: int | None
    heat_h_total: int | None
    label: Literal["calculated", "not_enough_data"]
    issued_at: datetime | None
    stale: bool
    history_status: Literal["ready", "loading", "empty"]


class HistoryStatusOut(ApiModel):
    model_config = ConfigDict(populate_by_name=True)

    years: list[int]
    from_date: date | None = Field(default=None, alias="from")
    to_date: date | None = Field(default=None, alias="to")
    days: int
    last_fetched_at: datetime | None
    status: Literal["ready", "loading", "empty"]
