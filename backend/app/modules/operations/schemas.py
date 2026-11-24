from __future__ import annotations

import enum
import uuid
from datetime import date as Date
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_serializer

from app.modules.operations.models import OperationType, ProductKind, ProductUnit, RateBasis


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


class ProductIn(BaseModel):
    name: str
    kind: ProductKind
    unit: ProductUnit
    active_ingredient: str | None = None
    nutrient_n_pct: OptionalDecimal = None
    nutrient_p2o5_pct: OptionalDecimal = None
    nutrient_k2o_pct: OptionalDecimal = None
    preharvest_interval_days: int | None = Field(default=None, ge=0)
    reentry_h: int | None = Field(default=None, ge=0)


class ProductPatch(BaseModel):
    name: str | None = None
    kind: ProductKind | None = None
    unit: ProductUnit | None = None
    active_ingredient: str | None = None
    nutrient_n_pct: OptionalDecimal = None
    nutrient_p2o5_pct: OptionalDecimal = None
    nutrient_k2o_pct: OptionalDecimal = None
    preharvest_interval_days: int | None = Field(default=None, ge=0)
    reentry_h: int | None = Field(default=None, ge=0)
    reason: str | None = None


class ProductOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    name: str
    kind: ProductKind
    unit: ProductUnit
    active_ingredient: str | None
    nutrient_n_pct: Decimal | None
    nutrient_p2o5_pct: Decimal | None
    nutrient_k2o_pct: Decimal | None
    preharvest_interval_days: int | None
    reentry_h: int | None
    version: int
    created_at: datetime
    updated_at: datetime


class ProductListOut(ApiModel):
    products: list[ProductOut]


class OperationProductIn(BaseModel):
    product_id: uuid.UUID
    rate: DecimalIn
    rate_unit: ProductUnit
    rate_basis: RateBasis
    water_l_ha: OptionalDecimal = None


class OperationSafetyIn(BaseModel):
    preharvest_interval_days: int | None = Field(default=None, ge=0)
    reentry_h: int | None = Field(default=None, ge=0)


class OperationIn(BaseModel):
    block_id: uuid.UUID
    valve_ids: list[uuid.UUID] = Field(default_factory=list)
    type: OperationType
    date: Date
    start_at: datetime | None = None
    duration_min: int | None = Field(default=None, ge=0)
    workers_count: int | None = Field(default=None, ge=0)
    target: str | None = None
    notes: str | None = None
    products: list[OperationProductIn] = Field(default_factory=list)
    safety: OperationSafetyIn | None = None


class OperationPatch(BaseModel):
    valve_ids: list[uuid.UUID] | None = None
    type: OperationType | None = None
    date: Date | None = None
    start_at: datetime | None = None
    duration_min: int | None = Field(default=None, ge=0)
    workers_count: int | None = Field(default=None, ge=0)
    target: str | None = None
    notes: str | None = None
    products: list[OperationProductIn] | None = None
    safety: OperationSafetyIn | None = None
    reason: str | None = None


class OperationProductOut(ApiModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    rate: Decimal
    rate_unit: ProductUnit
    rate_basis: RateBasis
    water_l_ha: Decimal | None
    total_qty: Decimal
    total_unit: ProductUnit
    source: Literal["calculated"] = "calculated"


class OperationSafetyOut(ApiModel):
    preharvest_interval_days: int | None
    reentry_h: int | None


class OperationOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    block_id: uuid.UUID
    valve_ids: list[uuid.UUID]
    type: OperationType
    date: Date
    start_at: datetime | None
    duration_min: int | None
    workers_count: int | None
    target: str | None
    notes: str | None
    area_ha: Decimal
    source: Literal["calculated"] = "calculated"
    products: list[OperationProductOut]
    safety: OperationSafetyOut | None
    version: int
    created_at: datetime
    updated_at: datetime


class OperationListOut(ApiModel):
    operations: list[OperationOut]


class JournalKind(enum.StrEnum):
    operation = "operation"
    irrigation = "irrigation"
    harvest = "harvest"
    stage = "stage"


class JournalItemOut(ApiModel):
    kind: JournalKind
    date: Date
    title: str
    details: str | None
    link_id: uuid.UUID
    source: Literal["measured", "estimated", "calculated", "entered"] | None = None
    operation_type: OperationType | None = None


class JournalListOut(ApiModel):
    items: list[JournalItemOut]


class StageAtBrief(ApiModel):
    id: uuid.UUID
    code: str
    name: dict[str, str]


class StageAtOut(ApiModel):
    stage: StageAtBrief | None
    date: Date | None
    label: Literal["observed", "predicted"] | None


class OperationProductPreviewIn(BaseModel):
    rate: DecimalIn
    rate_basis: RateBasis
    area_ha: DecimalIn
    water_l_ha: OptionalDecimal = None
    rate_unit: ProductUnit | None = None


class OperationProductPreviewOut(ApiModel):
    total_qty: Decimal
    total_unit: ProductUnit | None = None
    source: Literal["calculated"] = "calculated"


class ReentryOut(ApiModel):
    until: datetime
    product: str
