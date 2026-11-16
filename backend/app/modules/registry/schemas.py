"""Request and response models for registry calculations and blocks.

Display rounding lives here. Calculations keep full Decimal precision.
"""

import uuid
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_serializer

from app.modules.catalog.schemas import LocalizedName
from app.modules.registry.models import (
    BlockStatus,
    DensityInput,
    FlowEntryMode,
    IrrigationSystem,
    TypedFlowBasis,
)


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


def _parse_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("invalid integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("invalid integer") from exc
        if parsed.is_finite() and parsed == parsed.to_integral_value():
            return int(parsed)
    raise ValueError("invalid integer")


DecimalInput = Annotated[Decimal, BeforeValidator(_parse_decimal)]
IntInput = Annotated[int, BeforeValidator(_parse_int)]


def _format_places(value: Decimal | None, places: int) -> str | None:
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-places)
    return format(value.quantize(quantum, rounding=ROUND_HALF_UP), "f")


class PlantingPreviewIn(BaseModel):
    mode: Literal["spacing", "density", "count"]
    row_spacing_m: DecimalInput | None = None
    tree_spacing_m: DecimalInput | None = None
    trees_per_ha: IntInput | None = None
    trees_count: IntInput | None = None
    net_area_ha: DecimalInput | None = None


class PlantingPreviewOut(BaseModel):
    trees_per_ha: int | None
    tree_spacing_m: Decimal | None
    trees_in_block: int | None
    source: Literal["calculated"] = "calculated"

    @field_serializer("tree_spacing_m")
    def serialize_spacing(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)


class ValveIn(BaseModel):
    row_from: IntInput
    row_to: IntInput
    typed_q_m3h: DecimalInput | None = None


class ValveOut(BaseModel):
    row_from: int
    row_to: int
    rows: int | None
    area_ha: Decimal | None
    q_m3h: Decimal | None

    @field_serializer("area_ha")
    def serialize_area(self, value: Decimal | None) -> str | None:
        return _format_places(value, 4)

    @field_serializer("q_m3h")
    def serialize_flow(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)


class IrrigationPreviewIn(BaseModel):
    entry_mode: Literal["layout", "per_tree", "typed_flow"]
    row_spacing_m: DecimalInput | None = None
    laterals_per_row: IntInput | None = None
    emitter_spacing_m: DecimalInput | None = None
    emitter_flow_lph: DecimalInput | None = None
    trees_per_ha: IntInput | None = None
    emitters_per_tree: IntInput | None = None
    flow_per_emitter_lph: DecimalInput | None = None
    typed_flow_m3h: DecimalInput | None = None
    typed_flow_basis: Literal["block", "ha", "valve"] | None = None
    net_area_ha: DecimalInput | None = None
    valves: list[ValveIn] | None = None
    rows_total: IntInput | None = None


class IrrigationPreviewOut(BaseModel):
    q_ha_m3h: Decimal | None
    q_block_m3h: Decimal | None
    rate_mm_h: Decimal | None
    row_m_per_ha: Decimal | None = None
    lateral_m_per_ha: Decimal | None = None
    emitters_per_ha: Decimal | None = None
    valves: list[ValveOut]
    source: Literal["calculated"] = "calculated"

    @field_serializer("q_ha_m3h", "q_block_m3h", "rate_mm_h")
    def serialize_flow(self, value: Decimal | None) -> str | None:
        return _format_places(value, 2)

    @field_serializer("row_m_per_ha", "lateral_m_per_ha", "emitters_per_ha")
    def serialize_per_ha(self, value: Decimal | None) -> str | None:
        return _format_places(value, 0)


class GeometryPreviewIn(BaseModel):
    outline: dict[str, Any] | None = None
    row_line: dict[str, Any] | None = None


class GeometryPreviewOut(BaseModel):
    gross_area_ha: Decimal | None
    row_bearing_deg: Decimal | None
    source: Literal["calculated"] = "calculated"

    @field_serializer("gross_area_ha")
    def serialize_area(self, value: Decimal | None) -> str | None:
        return format_area_ha(value)

    @field_serializer("row_bearing_deg")
    def serialize_bearing(self, value: Decimal | None) -> str | None:
        return format_bearing_deg(value)


def format_area_ha(value: Decimal | None) -> str | None:
    return _format_places(value, 4)


def format_bearing_deg(value: Decimal | None) -> str | None:
    return _format_places(value, 1)


def format_flow_m3h(value: Decimal | None) -> str | None:
    return _format_places(value, 2)


def format_rate_mm_h(value: Decimal | None) -> str | None:
    return _format_places(value, 2)


def format_spacing_m(value: Decimal | None) -> str | None:
    return _format_places(value, 2)


SourceLabel = Literal["entered", "calculated"]


class BlockCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    outline: dict[str, Any] | None = None
    row_line: dict[str, Any] | None = None
    net_area_ha: DecimalInput | None = None
    crop_id: uuid.UUID | None = None
    training_system_id: uuid.UUID | None = None
    training_other: str | None = None
    rows_total: IntInput | None = None


class BlockUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    outline: dict[str, Any] | None = None
    row_line: dict[str, Any] | None = None
    net_area_ha: DecimalInput | None = None
    crop_id: uuid.UUID | None = None
    training_system_id: uuid.UUID | None = None
    training_other: str | None = None
    rows_total: IntInput | None = None
    reason: str | None = None


class BlockArchive(BaseModel):
    reason: str | None = None


class BlockCropOut(BaseModel):
    id: uuid.UUID
    code: str
    name: LocalizedName


class BlockSources(BaseModel):
    gross_area_ha: Literal["calculated"] = "calculated"
    row_bearing_deg: Literal["calculated"] = "calculated"
    net_area_ha: Literal["entered"] = "entered"


class BlockListItem(BaseModel):
    id: uuid.UUID
    name: str
    status: BlockStatus
    crop: BlockCropOut | None
    gross_area_ha: str | None
    net_area_ha: str | None
    trees_count: int | None = None
    q_block_m3h: str | None = None
    rate_mm_h: str | None = None
    outline: dict[str, Any] | None = None
    version: int


class PlantingIn(BaseModel):
    variety_id: uuid.UUID | None = None
    variety_text: str | None = None
    rootstock: str | None = None
    planting_year: IntInput | None = None
    density_input: DensityInput | None = None
    row_spacing_m: DecimalInput | None = None
    tree_spacing_m: DecimalInput | None = None
    trees_per_ha: IntInput | None = None
    trees_count: IntInput | None = None
    area_ha: DecimalInput | None = None


class PlantingsPut(BaseModel):
    plantings: list[PlantingIn] = Field(max_length=5)
    reason: str | None = None


class PlantingSources(BaseModel):
    row_spacing_m: SourceLabel | None = None
    tree_spacing_m: SourceLabel | None = None
    trees_per_ha: SourceLabel | None = None
    trees_count: SourceLabel | None = None
    area_ha: SourceLabel | None = None


class PlantingOut(BaseModel):
    id: uuid.UUID
    variety_id: uuid.UUID | None
    variety_text: str | None
    rootstock: str | None
    planting_year: int | None
    density_input: DensityInput | None
    row_spacing_m: Decimal | None
    tree_spacing_m: Decimal | None
    trees_per_ha: int | None
    trees_count: int | None
    area_ha: Decimal | None
    sort: int
    sources: PlantingSources

    @field_serializer("row_spacing_m", "tree_spacing_m")
    def serialize_spacing(self, value: Decimal | None) -> str | None:
        return format_spacing_m(value)

    @field_serializer("area_ha")
    def serialize_area(self, value: Decimal | None) -> str | None:
        return format_area_ha(value)


class IrrigationLayoutPut(BaseModel):
    system: IrrigationSystem
    entry_mode: FlowEntryMode
    laterals_per_row: IntInput | None = None
    emitter_spacing_m: DecimalInput | None = None
    emitter_flow_lph: DecimalInput | None = None
    emitters_per_tree: IntInput | None = None
    flow_per_emitter_lph: DecimalInput | None = None
    typed_flow_m3h: DecimalInput | None = None
    typed_flow_basis: TypedFlowBasis | None = None
    flow_meter: bool = False
    reason: str | None = None


class IrrigationLayoutSources(BaseModel):
    system: Literal["entered"] = "entered"
    entry_mode: Literal["entered"] = "entered"
    laterals_per_row: SourceLabel | None = None
    emitter_spacing_m: SourceLabel | None = None
    emitter_flow_lph: SourceLabel | None = None
    emitters_per_tree: SourceLabel | None = None
    flow_per_emitter_lph: SourceLabel | None = None
    typed_flow_m3h: SourceLabel | None = None
    typed_flow_basis: SourceLabel | None = None
    flow_meter: Literal["entered"] = "entered"
    q_ha_m3h: SourceLabel | None = None
    q_block_m3h: SourceLabel | None = None
    rate_mm_h: SourceLabel | None = None


class IrrigationLayoutOut(BaseModel):
    id: uuid.UUID
    system: IrrigationSystem
    entry_mode: FlowEntryMode
    laterals_per_row: int | None
    emitter_spacing_m: Decimal | None
    emitter_flow_lph: Decimal | None
    emitters_per_tree: int | None
    flow_per_emitter_lph: Decimal | None
    typed_flow_m3h: Decimal | None
    typed_flow_basis: TypedFlowBasis | None
    flow_meter: bool
    q_ha_m3h: Decimal | None
    q_block_m3h: Decimal | None
    rate_mm_h: Decimal | None
    sources: IrrigationLayoutSources

    @field_serializer(
        "emitter_spacing_m",
        "emitter_flow_lph",
        "flow_per_emitter_lph",
        "typed_flow_m3h",
        "q_ha_m3h",
        "q_block_m3h",
    )
    def serialize_flow(self, value: Decimal | None) -> str | None:
        return format_flow_m3h(value)

    @field_serializer("rate_mm_h")
    def serialize_rate(self, value: Decimal | None) -> str | None:
        return format_rate_mm_h(value)


class ValveWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    row_from: IntInput
    row_to: IntInput
    typed_q_m3h: DecimalInput | None = None


class ValvesPut(BaseModel):
    valves: list[ValveWrite]
    reason: str | None = None


class ValveSources(BaseModel):
    name: Literal["entered"] = "entered"
    row_from: Literal["entered"] = "entered"
    row_to: Literal["entered"] = "entered"
    typed_q_m3h: SourceLabel | None = None
    area_ha: SourceLabel | None = None
    q_m3h: SourceLabel | None = None


class BlockValveOut(BaseModel):
    id: uuid.UUID
    name: str
    sort: int
    row_from: int
    row_to: int
    typed_q_m3h: Decimal | None
    area_ha: Decimal | None
    q_m3h: Decimal | None
    sources: ValveSources

    @field_serializer("typed_q_m3h", "q_m3h")
    def serialize_flow(self, value: Decimal | None) -> str | None:
        return format_flow_m3h(value)

    @field_serializer("area_ha")
    def serialize_area(self, value: Decimal | None) -> str | None:
        return format_area_ha(value)


class BlockOut(BlockListItem):
    outline: dict[str, Any] | None
    row_line: dict[str, Any] | None
    row_bearing_deg: str | None
    rows_total: int | None
    training_system_id: uuid.UUID | None
    training_other: str | None
    sources: BlockSources = Field(default_factory=BlockSources)
    plantings: list[PlantingOut] = Field(default_factory=list)
    irrigation_layout: IrrigationLayoutOut | None = None
    valves: list[BlockValveOut] = Field(default_factory=list)


class BlockHistoryOut(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    version: int
    changed_fields: list[str]
    reason: str | None
    user_id: uuid.UUID
    changed_at: datetime
