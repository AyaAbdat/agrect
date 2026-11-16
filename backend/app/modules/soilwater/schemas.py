import enum
import uuid
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_serializer

from app.modules.catalog.schemas import LocalizedName
from app.modules.soilwater.models import (
    Compaction,
    DepthBand,
    InfiltrationSource,
    IrrigationSource,
    KcSource,
    SoilFeel,
    TextureMode,
    WbStatus,
)

SoilLabel = Literal["calculated", "not_enough_data"]
InfiltrationLabel = Literal["measured", "estimated", "entered"]


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, int) and not isinstance(value, bool):
        parsed = Decimal(value)
    elif isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid decimal") from exc
    else:
        raise ValueError("invalid decimal")
    if not parsed.is_finite():
        raise ValueError("invalid decimal")
    return parsed


def _parse_optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return _parse_decimal(value)


OptionalDecimal = Annotated[Decimal | None, BeforeValidator(_parse_optional_decimal)]


def _format_places(value: Decimal | None, places: int) -> str | None:
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-places)
    return format(value.quantize(quantum, rounding=ROUND_HALF_UP), "f")


def _format_number(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


class TextureClassOut(BaseModel):
    id: uuid.UUID
    code: str
    name: LocalizedName


class SoilSources(BaseModel):
    theta: Literal["calculated"] = "calculated"
    taw: Literal["calculated"] = "calculated"
    raw: Literal["calculated"] = "calculated"
    root_depth_m: Literal["entered"] = "entered"
    dry_down_pct: Literal["entered"] = "entered"
    full_on: Literal["entered"] = "entered"
    infiltration_mm_h: InfiltrationLabel = "entered"


class SoilPut(BaseModel):
    texture_mode: TextureMode
    texture_class_id: uuid.UUID | None = None
    sand_pct: OptionalDecimal = None
    silt_pct: OptionalDecimal = None
    clay_pct: OptionalDecimal = None
    root_depth_m: OptionalDecimal = None
    dry_down_pct: OptionalDecimal = None
    full_on: date | None = None
    organic_matter_pct: OptionalDecimal = None
    compaction: Compaction | None = None
    infiltration_mm_h: OptionalDecimal = None
    infiltration_source: InfiltrationSource | None = None
    reason: str | None = None


class SoilOut(BaseModel):
    texture_mode: TextureMode | None = None
    texture_class: TextureClassOut | None = None
    sand_pct: Decimal | None = None
    silt_pct: Decimal | None = None
    clay_pct: Decimal | None = None
    theta_fc: Decimal | None = None
    theta_wp: Decimal | None = None
    root_depth_m: Decimal | None = None
    dry_down_pct: Decimal | None = None
    full_on: date | None = None
    organic_matter_pct: Decimal | None = None
    compaction: Compaction | None = None
    infiltration_mm_h: Decimal | None = None
    infiltration_source: InfiltrationSource | None = None
    taw_mm: Decimal | None = None
    raw_mm: Decimal | None = None
    water_left_mm: Decimal | None = None
    irrigate_below_mm: Decimal | None = None
    label: SoilLabel
    sources: SoilSources
    version: int | None = None

    @field_serializer("sand_pct", "silt_pct", "clay_pct", "organic_matter_pct", "infiltration_mm_h")
    def serialize_number(self, value: Decimal | None) -> str | None:
        return _format_number(value)

    @field_serializer("theta_fc", "theta_wp")
    def serialize_theta(self, value: Decimal | None) -> str | None:
        return _format_places(value, 3)

    @field_serializer("root_depth_m")
    def serialize_depth(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)

    @field_serializer("dry_down_pct")
    def serialize_percent(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)

    @field_serializer("taw_mm", "raw_mm", "water_left_mm", "irrigate_below_mm")
    def serialize_store(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)


class IrrigationSettingsPut(BaseModel):
    efficiency: OptionalDecimal = None
    kc: OptionalDecimal = None
    kc_source: KcSource | None = None
    reason: str | None = None


class IrrigationSettingsOut(BaseModel):
    efficiency: Decimal | None = None
    kc: Decimal | None = None
    kc_source: KcSource | None = None
    version: int | None = None

    @field_serializer("efficiency")
    def serialize_efficiency(self, value: Decimal | None) -> str | None:
        return _format_places(value, 3)

    @field_serializer("kc")
    def serialize_kc(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)


class ApiModel(BaseModel):
    @field_serializer("*", mode="plain")
    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, enum.Enum):
            return value.value
        return value


class IrrigationEventIn(BaseModel):
    valve_ids: list[uuid.UUID] = Field(min_length=1)
    start_at: datetime
    duration_min: int = Field(gt=0)


class IrrigationEventPatch(BaseModel):
    valve_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    start_at: datetime | None = None
    duration_min: int | None = Field(default=None, gt=0)


class IrrigationEventOut(ApiModel):
    id: uuid.UUID
    block_id: uuid.UUID
    valve_ids: list[uuid.UUID]
    start_at: datetime
    duration_min: int
    depth_mm: Decimal
    volume_m3: Decimal
    soil_mm: Decimal
    runoff_mm: Decimal
    source: IrrigationSource
    version: int


class IrrigationTotalsOut(ApiModel):
    count: int
    depth_mm: Decimal
    volume_m3: Decimal
    soil_mm: Decimal


class IrrigationEventsOut(ApiModel):
    events: list[IrrigationEventOut]
    totals: IrrigationTotalsOut


class IrrigationPreviewIn(BaseModel):
    block_id: uuid.UUID
    valve_ids: list[uuid.UUID] = Field(min_length=1)
    duration_min: int = Field(gt=0)


class IrrigationPreviewOut(ApiModel):
    depth_mm: Decimal
    volume_m3: Decimal
    soil_mm: Decimal
    runoff_mm: Decimal
    source: Literal["calculated"] = "calculated"


class SoilCheckPreviewIn(BaseModel):
    feel: SoilFeel


class SoilCheckPreviewOut(ApiModel):
    reset_depletion_mm: Decimal
    water_left_mm: Decimal
    pct_of_taw: Decimal


BalancePeriod = Literal["week", "month", "season"]


class SoilCheckIn(BaseModel):
    date: date
    depth_band: DepthBand
    feel: SoilFeel


class SoilCheckOut(ApiModel):
    id: uuid.UUID
    block_id: uuid.UUID
    date: date
    depth_band: DepthBand
    feel: SoilFeel
    reset_depletion_mm: Decimal
    created_at: datetime


class WaterBalanceRowOut(ApiModel):
    date: date
    et0_mm: Decimal | None
    kc: Decimal | None
    etc_mm: Decimal | None
    rain_mm: Decimal | None
    irrigation_soil_mm: Decimal | None
    runoff_mm: Decimal | None
    drainage_mm: Decimal | None
    depletion_mm: Decimal | None
    taw_mm: Decimal | None
    raw_mm: Decimal | None
    water_left_mm: Decimal | None = None
    irrigate_below_mm: Decimal | None = None
    status: WbStatus
    is_forecast: bool
    inputs_hash: str


class WaterBalanceOut(ApiModel):
    rows: list[WaterBalanceRowOut]
    notes: list[str]


class DoseOut(ApiModel):
    net_mm: Decimal | None = None
    gross_mm: Decimal | None = None
    run_time_min: Decimal | None = None
    volume_m3: Decimal | None = None


class IrrigationTodayOut(ApiModel):
    date: date
    depletion_mm: Decimal | None
    taw_mm: Decimal | None
    raw_mm: Decimal | None
    water_left_mm: Decimal | None = None
    irrigate_below_mm: Decimal | None = None
    etc_today_mm: Decimal | None
    status: WbStatus
    refill: DoseOut
    maintain: DoseOut
    recommended: Literal["refill", "maintain"]
    label: Literal["calculated", "no_data"]
    missing: list[str]


class BlockIrrigationTodayOut(IrrigationTodayOut):
    block_id: uuid.UUID


class FarmIrrigationTodayOut(ApiModel):
    date: date
    blocks: list[BlockIrrigationTodayOut]
