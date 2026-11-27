from __future__ import annotations

import enum
import uuid
from datetime import date as Date
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, field_serializer

from app.modules.inputs.models import PriceResource, StockMoveKind
from app.modules.operations.models import OperationType


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


class PriceIn(BaseModel):
    resource: PriceResource
    product_id: uuid.UUID | None = None
    valid_from: Date
    dzd_per_unit: DecimalIn
    unit: str | None = None
    note: str | None = None


class PricePatch(BaseModel):
    valid_from: Date | None = None
    dzd_per_unit: OptionalDecimal = None
    note: str | None = None
    reason: str | None = None


class PriceOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    product_id: uuid.UUID | None
    resource: PriceResource
    valid_from: Date
    dzd_per_unit: Decimal
    unit: str
    note: str | None
    version: int
    created_at: datetime
    updated_at: datetime


class PriceListOut(ApiModel):
    prices: list[PriceOut]


class StockMoveIn(BaseModel):
    product_id: uuid.UUID
    date: Date
    qty: DecimalIn
    kind: StockMoveKind
    note: str | None = None


class StockMoveOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    product_id: uuid.UUID
    date: Date
    qty: Decimal
    kind: StockMoveKind
    operation_id: uuid.UUID | None
    note: str | None
    created_at: datetime


class StockMoveListOut(ApiModel):
    moves: list[StockMoveOut]


class StockItemOut(ApiModel):
    product_id: uuid.UUID
    product_name: str
    unit: str
    on_hand: Decimal
    last_purchase: Date | None
    uses_this_season: Decimal
    unit_mismatch_count: int
    low: bool | None


class StockOut(ApiModel):
    items: list[StockItemOut]


class CostByOperationOut(ApiModel):
    date: Date
    type: OperationType
    dzd: Decimal


class UnitMismatchOut(ApiModel):
    operation_id: uuid.UUID
    block_id: uuid.UUID
    block_name: str
    date: Date
    product: str
    operation_unit: str
    product_unit: str


class BlockCostsOut(ApiModel):
    season: int
    total_dzd: Decimal
    per_ha_dzd: Decimal | None
    by_source: dict[str, str]
    by_operation: list[CostByOperationOut]
    missing_prices: list[str]
    unit_mismatches: list[UnitMismatchOut]


class FarmCostBlockOut(ApiModel):
    block_id: uuid.UUID
    name: str
    total_dzd: Decimal
    per_ha_dzd: Decimal | None
    by_source: dict[str, str]


class FarmCostsOut(ApiModel):
    season: int
    blocks: list[FarmCostBlockOut]
    total_dzd: Decimal
    per_ha_dzd: Decimal | None
    missing_prices: list[str]
    unit_mismatches: list[UnitMismatchOut]
