import enum
import uuid
from datetime import date as Date
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_serializer

from app.modules.harvest.models import HarvestBasis, HarvestUnit

QualityField = Literal[
    "brix",
    "size_grade",
    "waste_pct",
    "moisture_pct",
    "protein_pct",
    "test_weight_kg_hl",
]


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
OptionalDecimal = Annotated[Decimal | None, BeforeValidator(_parse_optional_decimal)]


class ApiModel(BaseModel):
    @field_serializer("*", mode="plain")
    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, enum.Enum):
            return value.value
        return value


class HarvestQualityIn(BaseModel):
    brix: OptionalDecimal = None
    size_grade: dict[str, Any] | None = None
    waste_pct: OptionalDecimal = None
    moisture_pct: OptionalDecimal = None
    protein_pct: OptionalDecimal = None
    test_weight_kg_hl: OptionalDecimal = None


class HarvestQualityOut(ApiModel):
    brix: Decimal | None = None
    size_grade: dict[str, Any] | None = None
    waste_pct: Decimal | None = None
    moisture_pct: Decimal | None = None
    protein_pct: Decimal | None = None
    test_weight_kg_hl: Decimal | None = None


class HarvestEntryIn(BaseModel):
    date: Date
    pass_no: int = Field(default=1, ge=1)
    quantity: DecimalIn
    unit: HarvestUnit
    unit_weight_kg: OptionalDecimal = None
    basis: HarvestBasis
    valve_id: uuid.UUID | None = None
    basis_count: OptionalDecimal = None
    quality: HarvestQualityIn | None = None


class HarvestEntryPatch(BaseModel):
    date: Date | None = None
    pass_no: int | None = Field(default=None, ge=1)
    quantity: OptionalDecimal = None
    unit: HarvestUnit | None = None
    unit_weight_kg: OptionalDecimal = None
    basis: HarvestBasis | None = None
    valve_id: uuid.UUID | None = None
    basis_count: OptionalDecimal = None
    quality: HarvestQualityIn | None = None
    reason: str | None = None


class PreharvestWarningOut(ApiModel):
    product: str
    spray_date: Date
    days_since: int
    days_needed: int


class HarvestEntryOut(ApiModel):
    id: uuid.UUID
    block_id: uuid.UUID
    valve_id: uuid.UUID | None
    date: Date
    pass_no: int
    quantity: Decimal
    unit: HarvestUnit
    unit_weight_kg: Decimal | None
    basis: HarvestBasis
    basis_count: Decimal | None
    kg: Decimal
    kg_ha: Decimal
    area_ha: Decimal
    source: Literal["calculated"] = "calculated"
    quality: HarvestQualityOut | None = None
    preharvest_warning: PreharvestWarningOut | None = None
    version: int
    created_at: datetime
    updated_at: datetime


class HarvestListOut(ApiModel):
    entries: list[HarvestEntryOut]


class HarvestPreviewIn(BaseModel):
    block_id: uuid.UUID
    quantity: DecimalIn
    unit: HarvestUnit
    unit_weight_kg: OptionalDecimal = None
    basis: HarvestBasis
    valve_id: uuid.UUID | None = None
    basis_count: OptionalDecimal = None


class HarvestPreviewOut(ApiModel):
    kg: Decimal
    kg_ha: Decimal
    area_ha: Decimal
    source: Literal["calculated"] = "calculated"


class HarvestBlockSummaryOut(ApiModel):
    block_id: uuid.UUID
    kg_total: Decimal
    kg_ha: Decimal | None
    passes: int


class HarvestFarmTotalsOut(ApiModel):
    kg_total: Decimal
    kg_ha: Decimal | None
    blocks_harvested: int


class HarvestFarmSummaryOut(ApiModel):
    season: int
    farm: HarvestFarmTotalsOut
    blocks: list[HarvestBlockSummaryOut]


class HarvestFieldsOut(BaseModel):
    crop_id: uuid.UUID
    crop_code: str
    fields: list[QualityField]
