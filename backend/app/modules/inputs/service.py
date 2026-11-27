"""Inputs and cost: prices, stock moves, and cost lines.

Product uses and water cost lines are posted automatically from operations and
irrigation events through the in-process event bus. A cost line is written only
where a price exists for its date; a missing price is never an error.

Source: AGRECT system design — Inputs and cost.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.events import subscribe
from app.modules.auth.models import AppUser
from app.modules.equipment.models import MachineUse
from app.modules.farms.models import Farm
from app.modules.inputs import calc
from app.modules.inputs.models import (
    CostLine,
    CostRefKind,
    CostSource,
    Price,
    PriceResource,
    StockMove,
    StockMoveKind,
)
from app.modules.inputs.schemas import (
    BlockCostsOut,
    CostByOperationOut,
    FarmCostBlockOut,
    FarmCostsOut,
    PriceIn,
    PriceListOut,
    PriceOut,
    PricePatch,
    StockItemOut,
    StockMoveIn,
    StockMoveListOut,
    StockMoveOut,
    StockOut,
    UnitMismatchOut,
)
from app.modules.labour.models import LabourLog
from app.modules.operations.models import Operation, OperationProduct, Product
from app.modules.registry.models import Block, RecordVersion
from app.modules.soilwater.models import IrrigationEvent

_PRICE_ENTITY = "price"
_PRICE_FIELDS = ("valid_from", "dzd_per_unit", "note")

_RESOURCE_UNIT = {
    PriceResource.water_m3: "m3",
    PriceResource.labour_h: "h",
    PriceResource.machine_h: "h",
    PriceResource.energy_kwh: "kwh",
    PriceResource.fuel_l: "l",
}

# Resources priced per operation (labour, machine, fuel), in missing_prices order.
_OPERATION_RESOURCES = (PriceResource.labour_h, PriceResource.machine_h, PriceResource.fuel_l)


def _resource_code(resource: PriceResource) -> str:
    """Code sent in missing_prices for an unpriced resource, e.g. ``resource.labour_h``."""
    return f"resource.{resource.value}"


def _zone(farm: Farm) -> ZoneInfo:
    return ZoneInfo(farm.timezone)


def _local_date(ts: datetime, zone: ZoneInfo) -> date:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(zone).date()


def _hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _require_if_match(version: int, if_match: str | None) -> None:
    if if_match is None or if_match.strip() == "":
        raise AppError("conflict.version_required", 428)
    token = if_match.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        token = token[1:-1]
    try:
        presented = int(token)
    except ValueError:
        raise AppError("conflict.version", 409) from None
    if presented != version:
        raise AppError("conflict.version", 409)


def _require_reason(reason: str | None) -> str:
    cleaned = "" if reason is None else reason.strip()
    if cleaned == "":
        raise AppError("validation_error", 422, {"reason": "record.reason_required"})
    return cleaned


def _add_history(
    db: Session,
    *,
    farm_id: uuid.UUID,
    entity_id: uuid.UUID,
    version: int,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=farm_id,
            entity_type=_PRICE_ENTITY,
            entity_id=entity_id,
            version=version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


def _price_for(
    db: Session,
    farm_id: uuid.UUID,
    resource: PriceResource,
    product_id: uuid.UUID | None,
    on: date,
) -> Price | None:
    """Latest price for a resource whose valid_from is on or before ``on``."""
    stmt = select(Price).where(
        Price.farm_id == farm_id,
        Price.resource == resource,
        Price.valid_from <= on,
    )
    if product_id is None:
        stmt = stmt.where(Price.product_id.is_(None))
    else:
        stmt = stmt.where(Price.product_id == product_id)
    stmt = stmt.order_by(Price.valid_from.desc(), Price.created_at.desc())
    return db.scalars(stmt.limit(1)).first()


# --- posting ---------------------------------------------------------------


def _line_qty_in_product_unit(line: OperationProduct, product: Product) -> Decimal | None:
    try:
        return calc.convert_qty(line.total_qty, line.total_unit.value, product.unit.value)
    except calc.CalcInputError:
        return None


def _replace_operation_moves(db: Session, operation: Operation) -> None:
    db.execute(
        delete(StockMove).where(
            StockMove.operation_id == operation.id,
            StockMove.kind == StockMoveKind.use,
        )
    )
    for line in operation.products:
        product = line.product
        qty = _line_qty_in_product_unit(line, product)
        if qty is None:
            continue
        db.add(
            StockMove(
                farm_id=operation.farm_id,
                product_id=product.id,
                date=operation.date,
                qty=-qty,
                kind=StockMoveKind.use,
                operation_id=operation.id,
                user_id=operation.user_id,
            )
        )


def _replace_operation_cost(db: Session, operation: Operation) -> None:
    db.execute(
        delete(CostLine).where(
            CostLine.ref_kind == CostRefKind.operation,
            CostLine.ref_id == operation.id,
        )
    )
    for line in operation.products:
        product = line.product
        qty = _line_qty_in_product_unit(line, product)
        if qty is None:
            continue
        price = _price_for(db, operation.farm_id, PriceResource.product, product.id, operation.date)
        if price is None:
            continue
        dzd = calc.line_cost(qty, price.dzd_per_unit)
        db.add(
            CostLine(
                farm_id=operation.farm_id,
                block_id=operation.block_id,
                date=operation.date,
                source=CostSource.product,
                ref_kind=CostRefKind.operation,
                ref_id=operation.id,
                qty=qty,
                unit=product.unit.value,
                dzd=dzd,
                price_id=price.id,
                inputs_hash=_hash(
                    {
                        "qty": format(qty, "f"),
                        "price_id": str(price.id),
                        "date": operation.date.isoformat(),
                    }
                ),
            )
        )
    _add_labour_cost(db, operation)
    _add_machine_costs(db, operation)


def _resource_line(
    db: Session,
    operation: Operation,
    *,
    resource: PriceResource,
    source: CostSource,
    qty: Decimal,
    unit: str,
) -> None:
    """Cost line qty × price for a priced resource; nothing when no price exists."""
    price = _price_for(db, operation.farm_id, resource, None, operation.date)
    if price is None:
        return
    db.add(
        CostLine(
            farm_id=operation.farm_id,
            block_id=operation.block_id,
            date=operation.date,
            source=source,
            ref_kind=CostRefKind.operation,
            ref_id=operation.id,
            qty=qty,
            unit=unit,
            dzd=calc.line_cost(qty, price.dzd_per_unit),
            price_id=price.id,
            inputs_hash=_hash(
                {
                    "qty": format(qty, "f"),
                    "price_id": str(price.id),
                    "date": operation.date.isoformat(),
                }
            ),
        )
    )


def _add_machine_costs(db: Session, operation: Operation) -> None:
    """Machine line = Σ hours × machine_h price; fuel line = Σ fuel_l × fuel_l price."""
    uses = db.scalars(select(MachineUse).where(MachineUse.operation_id == operation.id)).all()
    if not uses:
        return
    _resource_line(
        db,
        operation,
        resource=PriceResource.machine_h,
        source=CostSource.machine,
        qty=sum((use.hours for use in uses), Decimal(0)),
        unit="h",
    )
    fuels = [use.fuel_l for use in uses if use.fuel_l is not None]
    if fuels:
        _resource_line(
            db,
            operation,
            resource=PriceResource.fuel_l,
            source=CostSource.fuel,
            qty=sum(fuels, Decimal(0)),
            unit="l",
        )


def _add_labour_cost(db: Session, operation: Operation) -> None:
    """Labour cost line (qty = total hours) when a labour_h price exists for the date."""
    log = db.scalar(select(LabourLog).where(LabourLog.operation_id == operation.id))
    if log is None:
        return
    price = _price_for(db, operation.farm_id, PriceResource.labour_h, None, operation.date)
    if price is None:
        return
    db.add(
        CostLine(
            farm_id=operation.farm_id,
            block_id=operation.block_id,
            date=operation.date,
            source=CostSource.labour,
            ref_kind=CostRefKind.operation,
            ref_id=operation.id,
            qty=log.total_hours,
            unit="h",
            dzd=calc.line_cost(log.total_hours, price.dzd_per_unit),
            price_id=price.id,
            inputs_hash=_hash(
                {
                    "qty": format(log.total_hours, "f"),
                    "price_id": str(price.id),
                    "date": operation.date.isoformat(),
                }
            ),
        )
    )


def _post_operation(db: Session, operation: Operation) -> None:
    _replace_operation_moves(db, operation)
    _replace_operation_cost(db, operation)


def _add_water_cost(
    db: Session, farm: Farm, block: Block, event: IrrigationEvent, on: date
) -> None:
    price = _price_for(db, farm.id, PriceResource.water_m3, None, on)
    if price is None:
        return
    dzd = calc.water_cost(event.volume_m3, price.dzd_per_unit)
    db.add(
        CostLine(
            farm_id=farm.id,
            block_id=block.id,
            date=on,
            source=CostSource.water,
            ref_kind=CostRefKind.irrigation,
            ref_id=event.id,
            qty=event.volume_m3,
            unit="m3",
            dzd=dzd,
            price_id=price.id,
            inputs_hash=_hash(
                {
                    "qty": format(event.volume_m3, "f"),
                    "price_id": str(price.id),
                    "date": on.isoformat(),
                }
            ),
        )
    )


def _load_operation(db: Session, operation_id: uuid.UUID) -> Operation | None:
    return db.scalar(
        select(Operation)
        .options(selectinload(Operation.products).selectinload(OperationProduct.product))
        .where(Operation.id == operation_id)
    )


def _on_operation_logged(payload: dict[str, Any]) -> None:
    db: Session = payload["db"]
    operation_id: uuid.UUID = payload["operation_id"]
    operation = _load_operation(db, operation_id)
    if operation is None:
        # Deleted: stock uses cascade away with the operation; clear cost lines.
        db.execute(
            delete(StockMove).where(
                StockMove.operation_id == operation_id,
                StockMove.kind == StockMoveKind.use,
            )
        )
        db.execute(
            delete(CostLine).where(
                CostLine.ref_kind == CostRefKind.operation,
                CostLine.ref_id == operation_id,
            )
        )
        return
    _post_operation(db, operation)


def _on_irrigation_logged(payload: dict[str, Any]) -> None:
    db: Session = payload["db"]
    block_id: uuid.UUID = payload["block_id"]
    from_date: date = payload["from_date"]
    block = db.get(Block, block_id)
    if block is None:
        return
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        return
    zone = _zone(farm)
    db.execute(
        delete(CostLine).where(
            CostLine.block_id == block_id,
            CostLine.source == CostSource.water,
            CostLine.date >= from_date,
        )
    )
    events = db.scalars(select(IrrigationEvent).where(IrrigationEvent.block_id == block_id)).all()
    for event in events:
        day = _local_date(event.start_at, zone)
        if day < from_date:
            continue
        _add_water_cost(db, farm, block, event, day)


def _recompute_products(db: Session, farm: Farm, product_id: uuid.UUID) -> None:
    operations = db.scalars(
        select(Operation)
        .options(selectinload(Operation.products).selectinload(OperationProduct.product))
        .where(
            Operation.farm_id == farm.id,
            Operation.id.in_(
                select(OperationProduct.operation_id).where(
                    OperationProduct.product_id == product_id
                )
            ),
        )
    ).all()
    for operation in operations:
        _replace_operation_cost(db, operation)


def _recompute_resource(db: Session, farm: Farm, resource: PriceResource) -> None:
    """Re-post the cost of every operation that uses a labour, machine or fuel resource."""
    if resource == PriceResource.labour_h:
        ids = select(LabourLog.operation_id).where(LabourLog.farm_id == farm.id)
    else:
        ids = select(MachineUse.operation_id).where(MachineUse.farm_id == farm.id)
    operations = db.scalars(
        select(Operation)
        .options(selectinload(Operation.products).selectinload(OperationProduct.product))
        .where(Operation.farm_id == farm.id, Operation.id.in_(ids))
    ).all()
    for operation in operations:
        _replace_operation_cost(db, operation)


def _recompute_water(db: Session, farm: Farm) -> None:
    db.execute(
        delete(CostLine).where(
            CostLine.farm_id == farm.id,
            CostLine.source == CostSource.water,
        )
    )
    zone = _zone(farm)
    events = db.scalars(select(IrrigationEvent).where(IrrigationEvent.farm_id == farm.id)).all()
    for event in events:
        block = db.get(Block, event.block_id)
        if block is None:
            continue
        _add_water_cost(db, farm, block, event, _local_date(event.start_at, zone))


def _recompute_after_price(
    db: Session,
    farm: Farm,
    resource: PriceResource,
    product_id: uuid.UUID | None,
) -> None:
    if resource == PriceResource.product and product_id is not None:
        _recompute_products(db, farm, product_id)
    elif resource == PriceResource.water_m3:
        _recompute_water(db, farm)
    elif resource in _OPERATION_RESOURCES:
        _recompute_resource(db, farm, resource)
    # energy has no cost lines yet (module comes later).


# --- prices ----------------------------------------------------------------


def _price_out(row: Price) -> PriceOut:
    return PriceOut(
        id=row.id,
        farm_id=row.farm_id,
        product_id=row.product_id,
        resource=row.resource,
        valid_from=row.valid_from,
        dzd_per_unit=row.dzd_per_unit,
        unit=row.unit,
        note=row.note,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _product_for_farm(db: Session, farm: Farm, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None or product.farm_id != farm.id:
        raise AppError("validation_error", 422, {"product_id": "inputs.product_not_in_farm"})
    return product


def _price_or_404(db: Session, user: AppUser, price_id: uuid.UUID) -> tuple[Price, Farm]:
    row = db.get(Price, price_id)
    if row is None:
        raise AppError("price.not_found", 404)
    farm = db.get(Farm, row.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("price.not_found", 404)
    return row, farm


def list_prices(db: Session, farm: Farm) -> PriceListOut:
    rows = db.scalars(
        select(Price)
        .where(Price.farm_id == farm.id)
        .order_by(Price.valid_from.desc(), Price.created_at.desc())
    ).all()
    return PriceListOut(prices=[_price_out(row) for row in rows])


def create_price(db: Session, farm: Farm, user: AppUser, body: PriceIn) -> PriceOut:
    if body.dzd_per_unit <= 0:
        raise AppError("validation_error", 422, {"dzd_per_unit": "inputs.price_must_be_positive"})
    if body.resource == PriceResource.product:
        if body.product_id is None:
            raise AppError("validation_error", 422, {"product_id": "inputs.product_required"})
        product = _product_for_farm(db, farm, body.product_id)
        unit = product.unit.value
        product_id: uuid.UUID | None = product.id
    else:
        if body.product_id is not None:
            raise AppError("validation_error", 422, {"product_id": "inputs.product_not_allowed"})
        unit = _RESOURCE_UNIT[body.resource]
        product_id = None
    now = datetime.now(UTC)
    row = Price(
        farm_id=farm.id,
        product_id=product_id,
        resource=body.resource,
        valid_from=body.valid_from,
        dzd_per_unit=body.dzd_per_unit,
        unit=unit,
        note=body.note,
        version=1,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    _add_history(
        db,
        farm_id=farm.id,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=list(_PRICE_FIELDS),
        reason=None,
    )
    _recompute_after_price(db, farm, body.resource, product_id)
    db.commit()
    db.refresh(row)
    return _price_out(row)


def update_price(
    db: Session,
    user: AppUser,
    price_id: uuid.UUID,
    body: PricePatch,
    if_match: str | None,
) -> PriceOut:
    row, farm = _price_or_404(db, user, price_id)
    _require_if_match(row.version, if_match)
    reason = _require_reason(body.reason)
    before = {field: getattr(row, field) for field in _PRICE_FIELDS}
    if body.valid_from is not None:
        row.valid_from = body.valid_from
    if body.dzd_per_unit is not None:
        if body.dzd_per_unit <= 0:
            raise AppError(
                "validation_error", 422, {"dzd_per_unit": "inputs.price_must_be_positive"}
            )
        row.dzd_per_unit = body.dzd_per_unit
    if "note" in body.model_fields_set:
        row.note = body.note
    changed = [field for field in _PRICE_FIELDS if getattr(row, field) != before[field]]
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(
        db,
        farm_id=farm.id,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=changed,
        reason=reason,
    )
    _recompute_after_price(db, farm, row.resource, row.product_id)
    db.commit()
    db.refresh(row)
    return _price_out(row)


def delete_price(
    db: Session,
    user: AppUser,
    price_id: uuid.UUID,
    if_match: str | None,
    reason: str | None,
) -> None:
    row, farm = _price_or_404(db, user, price_id)
    _require_if_match(row.version, if_match)
    cleaned = _require_reason(reason)
    resource = row.resource
    product_id = row.product_id
    row.version += 1
    _add_history(
        db,
        farm_id=farm.id,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=["deleted"],
        reason=cleaned,
    )
    db.delete(row)
    db.flush()
    _recompute_after_price(db, farm, resource, product_id)
    db.commit()


# --- stock moves -----------------------------------------------------------


def _move_out(row: StockMove) -> StockMoveOut:
    return StockMoveOut(
        id=row.id,
        farm_id=row.farm_id,
        product_id=row.product_id,
        date=row.date,
        qty=row.qty,
        kind=row.kind,
        operation_id=row.operation_id,
        note=row.note,
        created_at=row.created_at,
    )


def _move_or_404(db: Session, user: AppUser, move_id: uuid.UUID) -> StockMove:
    row = db.get(StockMove, move_id)
    if row is None:
        raise AppError("stock_move.not_found", 404)
    farm = db.get(Farm, row.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("stock_move.not_found", 404)
    return row


def list_stock_moves(db: Session, farm: Farm) -> StockMoveListOut:
    rows = db.scalars(
        select(StockMove)
        .where(StockMove.farm_id == farm.id)
        .order_by(StockMove.date.desc(), StockMove.created_at.desc())
    ).all()
    return StockMoveListOut(moves=[_move_out(row) for row in rows])


def create_stock_move(db: Session, farm: Farm, user: AppUser, body: StockMoveIn) -> StockMoveOut:
    if body.kind not in (StockMoveKind.purchase, StockMoveKind.adjustment):
        raise AppError("validation_error", 422, {"kind": "inputs.move_kind_not_allowed"})
    _product_for_farm(db, farm, body.product_id)
    row = StockMove(
        farm_id=farm.id,
        product_id=body.product_id,
        date=body.date,
        qty=body.qty,
        kind=body.kind,
        operation_id=None,
        note=body.note,
        user_id=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _move_out(row)


def delete_stock_move(db: Session, user: AppUser, move_id: uuid.UUID) -> None:
    row = _move_or_404(db, user, move_id)
    if row.kind == StockMoveKind.use:
        raise AppError("inputs.use_not_deletable", 409)
    db.delete(row)
    db.commit()


def _season_year(farm: Farm) -> int:
    return datetime.now(UTC).astimezone(_zone(farm)).date().year


def _mismatch_counts(db: Session, farm_id: uuid.UUID) -> dict[uuid.UUID, int]:
    lines = db.scalars(
        select(OperationProduct)
        .options(selectinload(OperationProduct.product))
        .join(Operation, OperationProduct.operation_id == Operation.id)
        .where(Operation.farm_id == farm_id)
    ).all()
    counts: dict[uuid.UUID, int] = {}
    for line in lines:
        product = line.product
        if product is None:
            continue
        if not calc.units_compatible(line.total_unit.value, product.unit.value):
            counts[product.id] = counts.get(product.id, 0) + 1
    return counts


def get_stock(db: Session, farm: Farm) -> StockOut:
    products = db.scalars(
        select(Product).where(Product.farm_id == farm.id).order_by(Product.name, Product.id)
    ).all()
    moves = db.scalars(select(StockMove).where(StockMove.farm_id == farm.id)).all()
    season = _season_year(farm)
    mismatch_counts = _mismatch_counts(db, farm.id)
    by_product: dict[uuid.UUID, list[StockMove]] = {}
    for move in moves:
        by_product.setdefault(move.product_id, []).append(move)
    items: list[StockItemOut] = []
    for product in products:
        product_moves = by_product.get(product.id, [])
        on_hand = sum((move.qty for move in product_moves), Decimal(0))
        uses = sum(
            (
                -move.qty
                for move in product_moves
                if move.kind == StockMoveKind.use and move.date.year == season
            ),
            Decimal(0),
        )
        purchases = [move.date for move in product_moves if move.kind == StockMoveKind.purchase]
        items.append(
            StockItemOut(
                product_id=product.id,
                product_name=product.name,
                unit=product.unit.value,
                on_hand=on_hand,
                last_purchase=max(purchases) if purchases else None,
                uses_this_season=uses,
                unit_mismatch_count=mismatch_counts.get(product.id, 0),
                low=None,
            )
        )
    return StockOut(items=items)


# --- costs -----------------------------------------------------------------


def _season_bounds(season: int) -> tuple[date, date]:
    return date(season, 1, 1), date(season, 12, 31)


def _block_cost_lines(db: Session, block_id: uuid.UUID, season: int) -> list[CostLine]:
    start, end = _season_bounds(season)
    return list(
        db.scalars(
            select(CostLine).where(
                CostLine.block_id == block_id,
                CostLine.date >= start,
                CostLine.date <= end,
            )
        ).all()
    )


def _block_names(db: Session, block_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not block_ids:
        return {}
    rows = db.execute(select(Block.id, Block.name).where(Block.id.in_(block_ids))).all()
    return {row[0]: row[1] for row in rows}


def _scan_operations(
    db: Session,
    farm_id: uuid.UUID,
    operations: list[Operation],
) -> tuple[list[str], list[UnitMismatchOut]]:
    """Products used without a price and operation lines whose unit cannot convert."""
    names: set[str] = set()
    mismatches: list[UnitMismatchOut] = []
    block_names = _block_names(db, {operation.block_id for operation in operations})
    for operation in operations:
        for line in operation.products:
            product = line.product
            if not calc.units_compatible(line.total_unit.value, product.unit.value):
                mismatches.append(
                    UnitMismatchOut(
                        operation_id=operation.id,
                        block_id=operation.block_id,
                        block_name=block_names.get(operation.block_id, ""),
                        date=operation.date,
                        product=product.name,
                        operation_unit=line.total_unit.value,
                        product_unit=product.unit.value,
                    )
                )
                continue
            price = _price_for(db, farm_id, PriceResource.product, product.id, operation.date)
            if price is None:
                names.add(product.name)
    missing = sorted(names) + [
        _resource_code(resource) for resource in _missing_resources(db, farm_id, operations)
    ]
    mismatches.sort(key=lambda row: (row.date, str(row.operation_id), row.product), reverse=True)
    return missing, mismatches


def _missing_resources(
    db: Session, farm_id: uuid.UUID, operations: list[Operation]
) -> list[PriceResource]:
    """Labour, machine and fuel used on a date that has no price, in label order."""
    if not operations:
        return []
    by_id = {operation.id: operation for operation in operations}
    used: dict[PriceResource, set[date]] = {resource: set() for resource in _OPERATION_RESOURCES}
    labour_ops = db.scalars(select(LabourLog.operation_id).where(LabourLog.operation_id.in_(by_id)))
    for op_id in labour_ops:
        used[PriceResource.labour_h].add(by_id[op_id].date)
    for use in db.scalars(select(MachineUse).where(MachineUse.operation_id.in_(by_id))):
        used[PriceResource.machine_h].add(by_id[use.operation_id].date)
        if use.fuel_l is not None:
            used[PriceResource.fuel_l].add(by_id[use.operation_id].date)
    return [
        resource
        for resource, days in used.items()
        if any(_price_for(db, farm_id, resource, None, day) is None for day in days)
    ]


def _season_operations(
    db: Session,
    *,
    farm_id: uuid.UUID,
    block_id: uuid.UUID | None,
    season: int,
) -> list[Operation]:
    start, end = _season_bounds(season)
    stmt = (
        select(Operation)
        .options(selectinload(Operation.products).selectinload(OperationProduct.product))
        .where(
            Operation.farm_id == farm_id,
            Operation.date >= start,
            Operation.date <= end,
        )
    )
    if block_id is not None:
        stmt = stmt.where(Operation.block_id == block_id)
    return list(db.scalars(stmt).all())


def block_costs(db: Session, block: Block, season: int | None) -> BlockCostsOut:
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    year = season if season is not None else _season_year(farm)
    lines = _block_cost_lines(db, block.id, year)
    total = sum((line.dzd for line in lines), Decimal(0))
    by_source: dict[str, Decimal] = {}
    for line in lines:
        by_source[line.source.value] = by_source.get(line.source.value, Decimal(0)) + line.dzd
    per_ha: Decimal | None = None
    if block.net_area_ha is not None and block.net_area_ha > 0:
        per_ha = calc.cost_per_ha(total, block.net_area_ha)
    ops: dict[uuid.UUID, Decimal] = {}
    for line in lines:
        if line.ref_kind == CostRefKind.operation:
            ops[line.ref_id] = ops.get(line.ref_id, Decimal(0)) + line.dzd
    by_operation: list[CostByOperationOut] = []
    if ops:
        operations = db.scalars(select(Operation).where(Operation.id.in_(list(ops.keys())))).all()
        operations.sort(key=lambda row: (row.date, str(row.id)), reverse=True)
        by_operation = [
            CostByOperationOut(date=row.date, type=row.type, dzd=ops[row.id]) for row in operations
        ]
    season_ops = _season_operations(db, farm_id=block.farm_id, block_id=block.id, season=year)
    missing_prices, unit_mismatches = _scan_operations(db, block.farm_id, season_ops)
    return BlockCostsOut(
        season=year,
        total_dzd=total,
        per_ha_dzd=per_ha,
        by_source={key: format(value, "f") for key, value in by_source.items()},
        by_operation=by_operation,
        missing_prices=missing_prices,
        unit_mismatches=unit_mismatches,
    )


def farm_costs(db: Session, farm: Farm, season: int | None) -> FarmCostsOut:
    year = season if season is not None else _season_year(farm)
    start, end = _season_bounds(year)
    blocks = db.scalars(
        select(Block).where(Block.farm_id == farm.id).order_by(Block.name, Block.id)
    ).all()
    lines = db.scalars(
        select(CostLine).where(
            CostLine.farm_id == farm.id,
            CostLine.date >= start,
            CostLine.date <= end,
        )
    ).all()
    totals: dict[uuid.UUID, Decimal] = {}
    sources: dict[uuid.UUID, dict[str, Decimal]] = {}
    for line in lines:
        totals[line.block_id] = totals.get(line.block_id, Decimal(0)) + line.dzd
        by_src = sources.setdefault(line.block_id, {})
        by_src[line.source.value] = by_src.get(line.source.value, Decimal(0)) + line.dzd
    block_rows: list[FarmCostBlockOut] = []
    farm_total = Decimal(0)
    farm_area = Decimal(0)
    for block in blocks:
        total = totals.get(block.id, Decimal(0))
        farm_total += total
        per_ha: Decimal | None = None
        if block.net_area_ha is not None and block.net_area_ha > 0:
            per_ha = calc.cost_per_ha(total, block.net_area_ha)
            farm_area += block.net_area_ha
        block_rows.append(
            FarmCostBlockOut(
                block_id=block.id,
                name=block.name,
                total_dzd=total,
                per_ha_dzd=per_ha,
                by_source={
                    key: format(value, "f") for key, value in sources.get(block.id, {}).items()
                },
            )
        )
    farm_per_ha = calc.cost_per_ha(farm_total, farm_area) if farm_area > 0 else None
    season_ops = _season_operations(db, farm_id=farm.id, block_id=None, season=year)
    missing_prices, unit_mismatches = _scan_operations(db, farm.id, season_ops)
    return FarmCostsOut(
        season=year,
        blocks=block_rows,
        total_dzd=farm_total,
        per_ha_dzd=farm_per_ha,
        missing_prices=missing_prices,
        unit_mismatches=unit_mismatches,
    )


# --- event wiring ----------------------------------------------------------

_registered = False


def register_handlers() -> None:
    global _registered
    if _registered:
        return
    subscribe("operation.logged", _on_operation_logged)
    subscribe("irrigation.logged", _on_irrigation_logged)
    _registered = True


register_handlers()
