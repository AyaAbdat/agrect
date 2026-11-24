"""Request and response models for the fertigation station.

Decimals travel as JSON strings. Calculations keep full Decimal precision.
"""

import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_serializer

from app.modules.station.models import CapacityChoice, CapacityMode, WaterSourceKind


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


DecimalIn = Annotated[Decimal, BeforeValidator(_parse_decimal)]
OptionalDecimalIn = Annotated[Decimal | None, BeforeValidator(_parse_optional_decimal)]


class JsonModel(BaseModel):
    @field_serializer("*", mode="plain")
    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, enum.Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, time):
            return value.isoformat()
        if isinstance(value, uuid.UUID):
            return str(value)
        return value


class WaterSourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    kind: WaterSourceKind
    ec_ds_m: OptionalDecimalIn = None
    basin_volume_m3: OptionalDecimalIn = None


class WaterSourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    kind: WaterSourceKind | None = None
    ec_ds_m: OptionalDecimalIn = None
    basin_volume_m3: OptionalDecimalIn = None


class WaterSourceOut(JsonModel):
    id: uuid.UUID
    name: str
    kind: WaterSourceKind
    ec_ds_m: Decimal | None
    basin_volume_m3: Decimal | None


class PumpIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    flow_m3h: DecimalIn
    serves_all_blocks: bool = True
    pressure_bar: OptionalDecimalIn = None
    water_source_id: uuid.UUID | None = None
    block_ids: list[uuid.UUID] | None = None


class PumpPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    flow_m3h: OptionalDecimalIn = None
    serves_all_blocks: bool | None = None
    pressure_bar: OptionalDecimalIn = None
    water_source_id: uuid.UUID | None = None


class WindowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_time: str
    end_time: str


class WindowsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    windows: list[WindowIn]


class BlocksPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_ids: list[uuid.UUID]


class PumpBlockOut(JsonModel):
    id: uuid.UUID
    name: str


class PumpWindowOut(JsonModel):
    id: uuid.UUID
    start_time: time
    end_time: time


class PumpOut(JsonModel):
    id: uuid.UUID
    name: str
    flow_m3h: Decimal
    serves_all_blocks: bool
    pressure_bar: Decimal | None
    version: int
    blocks: list[PumpBlockOut]
    windows: list[PumpWindowOut]
    water_source: WaterSourceOut | None


class StationOut(JsonModel):
    id: uuid.UUID
    name: str
    version: int
    created_at: datetime
    updated_at: datetime


class StationTotals(JsonModel):
    pumps_flow_m3h: Decimal


class FarmStationOut(JsonModel):
    station: StationOut | None
    pumps: list[PumpOut]
    water_sources: list[WaterSourceOut]
    totals: StationTotals


class ValveFlowOut(JsonModel):
    valve_id: uuid.UUID
    block_id: uuid.UUID
    q_m3h: Decimal
    run_time_min: Decimal


class ShiftOut(JsonModel):
    valves: list[ValveFlowOut]
    flow_m3h: Decimal
    time_min: Decimal


class CapacitySummaryOut(JsonModel):
    open_together_flow_m3h: Decimal
    pumps_flow_m3h: Decimal
    short_by_m3h: Decimal
    hours_needed: Decimal
    hours_available: Decimal | None
    fits_in_hours: bool | None


class CapacityCheckOut(JsonModel):
    mode: CapacityMode
    source: Literal["calculated"]
    summary: CapacitySummaryOut
    shifts: list[ShiftOut]
    cannot_supply: list[ValveFlowOut]
    no_dose_blocks: list[uuid.UUID]


class CapacityDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice: CapacityChoice
    reason: str
    block_ids: list[uuid.UUID] | None = None
    mode: CapacityMode = CapacityMode.today


class CapacityDecisionOut(JsonModel):
    id: uuid.UUID
    choice: CapacityChoice
    reason: str
    block_ids: list[uuid.UUID] | None
    mode: CapacityMode
    snapshot: CapacityCheckOut
    created_at: datetime
