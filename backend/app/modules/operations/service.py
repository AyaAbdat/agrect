"""Field operations and farm product list: totals, safety, re-entry."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.events import publish
from app.modules.auth.models import AppUser
from app.modules.catalog.models import StageDef
from app.modules.equipment.service import (
    apply_operation_machines,
    operation_machine_warnings,
    operation_machines_out,
)
from app.modules.farms.models import Farm
from app.modules.harvest.models import HarvestEntry
from app.modules.inputs import calc as inputs_calc
from app.modules.inputs.models import CostLine, CostRefKind
from app.modules.labour.service import (
    apply_operation_labour,
    operation_labour_out,
    operation_labour_warnings,
)
from app.modules.operations import calc
from app.modules.operations.models import (
    Operation,
    OperationProduct,
    OperationSafety,
    OperationType,
    Product,
)
from app.modules.operations.schemas import (
    JournalItemOut,
    JournalKind,
    JournalListOut,
    OperationIn,
    OperationListOut,
    OperationOut,
    OperationPatch,
    OperationProductIn,
    OperationProductOut,
    OperationProductPreviewIn,
    OperationProductPreviewOut,
    OperationSafetyIn,
    OperationSafetyOut,
    OperationWarningOut,
    ProductIn,
    ProductListOut,
    ProductOut,
    ProductPatch,
    ReentryOut,
    StageAtBrief,
    StageAtOut,
)
from app.modules.phenology.models import (
    BlockSeason,
    PredictionLabel,
    StageObservation,
    StagePrediction,
)
from app.modules.registry.models import Block, RecordVersion, Valve
from app.modules.soilwater.models import IrrigationEvent

_ENTITY_OPERATION = "operation"
_ENTITY_PRODUCT = "product"

_SPRAY_TYPES = frozenset(
    {
        OperationType.crop_protection_spray,
        OperationType.herbicide,
        OperationType.growth_regulator,
        OperationType.foliar_application,
    }
)

_PRODUCT_FIELDS = (
    "name",
    "kind",
    "unit",
    "active_ingredient",
    "nutrient_n_pct",
    "nutrient_p2o5_pct",
    "nutrient_k2o_pct",
    "preharvest_interval_days",
    "reentry_h",
)

_OPERATION_FIELDS = (
    "block_id",
    "valve_ids",
    "type",
    "date",
    "start_at",
    "duration_min",
    "workers_count",
    "target",
    "notes",
    "area_ha",
)

_TYPE_TITLE = {
    OperationType.fertigation: "Fertigation",
    OperationType.foliar_application: "Foliar application",
    OperationType.crop_protection_spray: "Treatment",
    OperationType.herbicide: "Weed control",
    OperationType.pruning: "Pruning",
    OperationType.shoot_cluster_thinning: "Thinning",
    OperationType.growth_regulator: "Growth regulator",
    OperationType.girdling: "Girdling",
    OperationType.leaf_removal: "Leaf removal",
    OperationType.cover_netting: "Cover netting",
    OperationType.tillage: "Tillage",
    OperationType.sowing: "Sowing",
    OperationType.nitrogen_application: "Nitrogen application",
    OperationType.other: "Other",
}


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


def _clean_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    stripped = reason.strip()
    if not stripped:
        return None
    return stripped


def _clean_name(name: str | None) -> str:
    if name is None:
        return ""
    return name.strip()


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _add_history(
    db: Session,
    *,
    farm_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    version: int,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=farm_id,
            entity_type=entity_type,
            entity_id=entity_id,
            version=version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


def _product_out(row: Product) -> ProductOut:
    return ProductOut(
        id=row.id,
        farm_id=row.farm_id,
        name=row.name,
        kind=row.kind,
        unit=row.unit,
        active_ingredient=row.active_ingredient,
        nutrient_n_pct=row.nutrient_n_pct,
        nutrient_p2o5_pct=row.nutrient_p2o5_pct,
        nutrient_k2o_pct=row.nutrient_k2o_pct,
        preharvest_interval_days=row.preharvest_interval_days,
        reentry_h=row.reentry_h,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _product_or_404(db: Session, user: AppUser, product_id: uuid.UUID) -> Product:
    row = db.get(Product, product_id)
    if row is None:
        raise AppError("product.not_found", 404)
    farm = db.get(Farm, row.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("product.not_found", 404)
    return row


def _name_taken(
    db: Session,
    farm_id: uuid.UUID,
    name: str,
    product_id: uuid.UUID | None,
) -> bool:
    stmt = select(Product.id).where(Product.farm_id == farm_id, Product.name == name)
    if product_id is not None:
        stmt = stmt.where(Product.id != product_id)
    return db.scalar(stmt.limit(1)) is not None


def list_products(db: Session, farm: Farm) -> ProductListOut:
    rows = db.scalars(
        select(Product).where(Product.farm_id == farm.id).order_by(Product.name, Product.id)
    ).all()
    return ProductListOut(products=[_product_out(row) for row in rows])


def create_product(db: Session, farm: Farm, user: AppUser, body: ProductIn) -> ProductOut:
    name = _clean_name(body.name)
    if not name:
        raise AppError("validation_error", 422, {"name": "operations.product_name_required"})
    if _name_taken(db, farm.id, name, None):
        raise AppError("validation_error", 422, {"name": "operations.product_name_taken"})
    now = datetime.now(UTC)
    row = Product(
        farm_id=farm.id,
        name=name,
        kind=body.kind,
        unit=body.unit,
        active_ingredient=body.active_ingredient,
        nutrient_n_pct=body.nutrient_n_pct,
        nutrient_p2o5_pct=body.nutrient_p2o5_pct,
        nutrient_k2o_pct=body.nutrient_k2o_pct,
        preharvest_interval_days=body.preharvest_interval_days,
        reentry_h=body.reentry_h,
        version=1,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    _add_history(
        db,
        farm_id=farm.id,
        entity_type=_ENTITY_PRODUCT,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=list(_PRODUCT_FIELDS),
        reason=None,
    )
    db.commit()
    db.refresh(row)
    return _product_out(row)


def update_product(
    db: Session,
    user: AppUser,
    product_id: uuid.UUID,
    body: ProductPatch,
    if_match: str | None,
) -> ProductOut:
    row = _product_or_404(db, user, product_id)
    _require_if_match(row.version, if_match)
    before = {field: getattr(row, field) for field in _PRODUCT_FIELDS}
    if body.name is not None:
        name = _clean_name(body.name)
        if not name:
            raise AppError("validation_error", 422, {"name": "operations.product_name_required"})
        if _name_taken(db, row.farm_id, name, row.id):
            raise AppError("validation_error", 422, {"name": "operations.product_name_taken"})
        row.name = name
    if body.kind is not None:
        row.kind = body.kind
    if body.unit is not None:
        row.unit = body.unit
    if "active_ingredient" in body.model_fields_set:
        row.active_ingredient = body.active_ingredient
    if "nutrient_n_pct" in body.model_fields_set:
        row.nutrient_n_pct = body.nutrient_n_pct
    if "nutrient_p2o5_pct" in body.model_fields_set:
        row.nutrient_p2o5_pct = body.nutrient_p2o5_pct
    if "nutrient_k2o_pct" in body.model_fields_set:
        row.nutrient_k2o_pct = body.nutrient_k2o_pct
    if "preharvest_interval_days" in body.model_fields_set:
        row.preharvest_interval_days = body.preharvest_interval_days
    if "reentry_h" in body.model_fields_set:
        row.reentry_h = body.reentry_h
    changed = [field for field in _PRODUCT_FIELDS if getattr(row, field) != before[field]]
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_PRODUCT,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=changed,
        reason=_clean_reason(body.reason),
    )
    db.commit()
    db.refresh(row)
    return _product_out(row)


def delete_product(
    db: Session,
    user: AppUser,
    product_id: uuid.UUID,
    if_match: str | None,
    reason: str | None = None,
) -> None:
    row = _product_or_404(db, user, product_id)
    _require_if_match(row.version, if_match)
    in_use = db.scalar(
        select(OperationProduct.id).where(OperationProduct.product_id == row.id).limit(1)
    )
    if in_use is not None:
        raise AppError("operations.product_in_use", 409)
    row.version += 1
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_PRODUCT,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=["deleted"],
        reason=_clean_reason(reason),
    )
    db.delete(row)
    db.commit()


def _block_for_farm(db: Session, farm: Farm, block_id: uuid.UUID) -> Block:
    block = db.get(Block, block_id)
    if block is None or block.farm_id != farm.id:
        raise AppError("validation_error", 422, {"block_id": "operations.block_not_in_farm"})
    return block


def _operation_or_404(db: Session, user: AppUser, operation_id: uuid.UUID) -> Operation:
    row = db.scalar(
        select(Operation)
        .options(
            selectinload(Operation.products).selectinload(OperationProduct.product),
            selectinload(Operation.safety),
        )
        .where(Operation.id == operation_id)
    )
    if row is None:
        raise AppError("operation.not_found", 404)
    farm = db.get(Farm, row.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("operation.not_found", 404)
    return row


def _chosen_valves(
    db: Session,
    block: Block,
    valve_ids: list[uuid.UUID],
) -> list[Valve]:
    unique_ids = list(dict.fromkeys(valve_ids))
    if not unique_ids:
        return []
    found = db.scalars(
        select(Valve).where(
            Valve.id.in_(unique_ids),
            Valve.block_id == block.id,
            Valve.farm_id == block.farm_id,
        )
    ).all()
    by_id = {valve.id: valve for valve in found}
    if set(unique_ids) != set(by_id):
        raise AppError("validation_error", 422, {"valve_ids": "operations.valve_not_in_block"})
    return [by_id[valve_id] for valve_id in unique_ids]


def _area_for(
    db: Session,
    block: Block,
    valve_ids: list[uuid.UUID],
) -> tuple[list[uuid.UUID], Decimal]:
    valves = _chosen_valves(db, block, valve_ids)
    net = block.net_area_ha
    if net is None:
        raise AppError("validation_error", 422, {"net_area_ha": "operations.net_area_required"})
    try:
        if valves:
            areas = []
            for valve in valves:
                if valve.area_ha is None:
                    raise calc.CalcInputError("valve_areas_ha", "operations.valve_area_required")
                areas.append(valve.area_ha)
            area = calc.area_worked_ha(net, areas)
        else:
            area = calc.area_worked_ha(net, None)
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
    return [valve.id for valve in valves], area


def _load_products(
    db: Session,
    farm_id: uuid.UUID,
    lines: list[OperationProductIn],
) -> list[tuple[OperationProductIn, Product]]:
    if not lines:
        return []
    ids = [line.product_id for line in lines]
    found = db.scalars(select(Product).where(Product.id.in_(ids), Product.farm_id == farm_id)).all()
    by_id = {row.id: row for row in found}
    paired: list[tuple[OperationProductIn, Product]] = []
    for line in lines:
        product = by_id.get(line.product_id)
        if product is None:
            raise AppError(
                "validation_error",
                422,
                {"products": "operations.product_not_in_farm"},
            )
        paired.append((line, product))
    return paired


def _line_total(
    line: OperationProductIn,
    area_ha: Decimal,
) -> Decimal:
    try:
        return calc.product_total(
            line.rate,
            line.rate_basis.value,  # type: ignore[arg-type]
            area_ha,
            line.water_l_ha,
        )
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None


def _default_safety(
    paired: list[tuple[OperationProductIn, Product]],
    override: OperationSafetyIn | None,
) -> OperationSafetyOut | None:
    if override is not None:
        return OperationSafetyOut(
            preharvest_interval_days=override.preharvest_interval_days,
            reentry_h=override.reentry_h,
        )
    best: Product | None = None
    best_phi = -1
    for _line, product in paired:
        phi = product.preharvest_interval_days
        if phi is None:
            continue
        if phi > best_phi:
            best_phi = phi
            best = product
    if best is None:
        has_reentry = any(product.reentry_h is not None for _line, product in paired)
        if not has_reentry:
            return None
        # No PHI on any product; copy the longest re-entry alone.
        best_re = -1
        reentry_product: Product | None = None
        for _line, product in paired:
            hours = product.reentry_h
            if hours is None:
                continue
            if hours > best_re:
                best_re = hours
                reentry_product = product
        if reentry_product is None:
            return None
        return OperationSafetyOut(
            preharvest_interval_days=None,
            reentry_h=reentry_product.reentry_h,
        )
    return OperationSafetyOut(
        preharvest_interval_days=best.preharvest_interval_days,
        reentry_h=best.reentry_h,
    )


def _apply_products(
    row: Operation,
    paired: list[tuple[OperationProductIn, Product]],
    area_ha: Decimal,
) -> None:
    row.products.clear()
    for line, product in paired:
        total = _line_total(line, area_ha)
        row.products.append(
            OperationProduct(
                product_id=product.id,
                rate=line.rate,
                rate_unit=line.rate_unit,
                rate_basis=line.rate_basis,
                water_l_ha=line.water_l_ha,
                total_qty=total,
                total_unit=line.rate_unit,
            )
        )


def _apply_safety(row: Operation, safety: OperationSafetyOut | None) -> None:
    if safety is None:
        row.safety = None
        return
    if row.safety is None:
        row.safety = OperationSafety(operation_id=row.id)
    row.safety.preharvest_interval_days = safety.preharvest_interval_days
    row.safety.reentry_h = safety.reentry_h


def _operation_cost_dzd(db: Session, operation_id: uuid.UUID) -> Decimal | None:
    """Sum of the operation's product cost lines; None when none exist (no price)."""
    totals = db.scalars(
        select(CostLine.dzd).where(
            CostLine.ref_kind == CostRefKind.operation,
            CostLine.ref_id == operation_id,
        )
    ).all()
    if not totals:
        return None
    return sum(totals, Decimal(0))


def _operation_warnings(db: Session, row: Operation) -> list[OperationWarningOut]:
    warnings: list[OperationWarningOut] = []
    for line in row.products:
        product = line.product
        if product is None:
            continue
        if not inputs_calc.units_compatible(line.total_unit.value, product.unit.value):
            warnings.append(OperationWarningOut(code="inputs.unit_mismatch", product=product.name))
    warnings.extend(operation_labour_warnings(db, row.id))
    warnings.extend(operation_machine_warnings(db, row.id))
    return warnings


def _operation_out(db: Session, row: Operation) -> OperationOut:
    products = [
        OperationProductOut(
            id=line.id,
            product_id=line.product_id,
            product_name=line.product.name if line.product is not None else "",
            rate=line.rate,
            rate_unit=line.rate_unit,
            rate_basis=line.rate_basis,
            water_l_ha=line.water_l_ha,
            total_qty=line.total_qty,
            total_unit=line.total_unit,
            source="calculated",
        )
        for line in row.products
    ]
    safety = None
    if row.safety is not None:
        safety = OperationSafetyOut(
            preharvest_interval_days=row.safety.preharvest_interval_days,
            reentry_h=row.safety.reentry_h,
        )
    return OperationOut(
        id=row.id,
        farm_id=row.farm_id,
        block_id=row.block_id,
        valve_ids=list(row.valve_ids or []),
        type=row.type,
        date=row.date,
        start_at=row.start_at,
        duration_min=row.duration_min,
        workers_count=row.workers_count,
        target=row.target,
        notes=row.notes,
        area_ha=row.area_ha,
        source="calculated",
        products=products,
        safety=safety,
        labour=operation_labour_out(db, row.id),
        machines=operation_machines_out(db, row),
        cost_dzd=_operation_cost_dzd(db, row.id),
        warnings=_operation_warnings(db, row),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def list_operations(
    db: Session,
    farm: Farm,
    *,
    block_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> OperationListOut:
    stmt = (
        select(Operation)
        .options(
            selectinload(Operation.products).selectinload(OperationProduct.product),
            selectinload(Operation.safety),
        )
        .where(Operation.farm_id == farm.id)
    )
    if block_id is not None:
        stmt = stmt.where(Operation.block_id == block_id)
    if date_from is not None:
        stmt = stmt.where(Operation.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Operation.date <= date_to)
    rows = db.scalars(stmt.order_by(Operation.date.desc(), Operation.id.desc())).all()
    return OperationListOut(operations=[_operation_out(db, row) for row in rows])


def get_operation(db: Session, user: AppUser, operation_id: uuid.UUID) -> OperationOut:
    return _operation_out(db, _operation_or_404(db, user, operation_id))


def create_operation(
    db: Session,
    farm: Farm,
    user: AppUser,
    body: OperationIn,
) -> OperationOut:
    block = _block_for_farm(db, farm, body.block_id)
    valve_ids, area = _area_for(db, block, body.valve_ids)
    paired = _load_products(db, farm.id, body.products)
    safety = _default_safety(paired, body.safety)
    now = datetime.now(UTC)
    row = Operation(
        farm_id=farm.id,
        block_id=block.id,
        valve_ids=valve_ids,
        type=body.type,
        date=body.date,
        start_at=None if body.start_at is None else _aware(body.start_at),
        duration_min=body.duration_min,
        workers_count=body.workers_count,
        target=_clean_reason(body.target),
        notes=body.notes,
        area_ha=area,
        user_id=user.id,
        version=1,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    _apply_products(row, paired, area)
    _apply_safety(row, safety)
    if body.labour is not None:
        row.workers_count = apply_operation_labour(db, row, body.labour)
    apply_operation_machines(db, row, body.machines)
    _add_history(
        db,
        farm_id=farm.id,
        entity_type=_ENTITY_OPERATION,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=list(_OPERATION_FIELDS) + ["products", "safety", "labour", "machines"],
        reason=None,
    )
    db.flush()
    publish("operation.logged", {"db": db, "operation_id": row.id})
    db.commit()
    return _operation_out(db, _operation_or_404(db, user, row.id))


def update_operation(
    db: Session,
    user: AppUser,
    operation_id: uuid.UUID,
    body: OperationPatch,
    if_match: str | None,
) -> OperationOut:
    row = _operation_or_404(db, user, operation_id)
    _require_if_match(row.version, if_match)
    before = {field: getattr(row, field) for field in _OPERATION_FIELDS}
    farm = db.get(Farm, row.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    block = db.get(Block, row.block_id)
    if block is None:
        raise AppError("block.not_found", 404)
    valve_ids = list(row.valve_ids or []) if body.valve_ids is None else body.valve_ids
    stored_ids, area = _area_for(db, block, valve_ids)
    if body.type is not None:
        row.type = body.type
    if body.date is not None:
        row.date = body.date
    if "start_at" in body.model_fields_set:
        row.start_at = None if body.start_at is None else _aware(body.start_at)
    if "duration_min" in body.model_fields_set:
        row.duration_min = body.duration_min
    if "workers_count" in body.model_fields_set:
        row.workers_count = body.workers_count
    if "target" in body.model_fields_set:
        row.target = _clean_reason(body.target)
    if "notes" in body.model_fields_set:
        row.notes = body.notes
    row.valve_ids = stored_ids
    row.area_ha = area
    products_changed = False
    if body.products is not None:
        paired = _load_products(db, farm.id, body.products)
        _apply_products(row, paired, area)
        products_changed = True
    else:
        # Recompute totals when area changes.
        for line in row.products:
            try:
                line.total_qty = calc.product_total(
                    line.rate,
                    line.rate_basis.value,  # type: ignore[arg-type]
                    area,
                    line.water_l_ha,
                )
            except calc.CalcInputError as exc:
                raise AppError("validation_error", 422, {exc.field: exc.code}) from None
            line.total_unit = line.rate_unit
        paired = [
            (
                OperationProductIn(
                    product_id=line.product_id,
                    rate=line.rate,
                    rate_unit=line.rate_unit,
                    rate_basis=line.rate_basis,
                    water_l_ha=line.water_l_ha,
                ),
                line.product,
            )
            for line in row.products
        ]
    safety_changed = False
    if body.safety is not None:
        _apply_safety(row, _default_safety(paired, body.safety))
        safety_changed = True
    elif products_changed:
        _apply_safety(row, _default_safety(paired, None))
        safety_changed = True
    labour_changed = "labour" in body.model_fields_set
    if labour_changed:
        # Clearing labour also clears its alias workers_count (D-079).
        row.workers_count = apply_operation_labour(db, row, body.labour)
    machines_changed = body.machines is not None
    if body.machines is not None:
        apply_operation_machines(db, row, body.machines)
    changed = [field for field in _OPERATION_FIELDS if getattr(row, field) != before[field]]
    if products_changed:
        changed.append("products")
    if safety_changed:
        changed.append("safety")
    if labour_changed:
        changed.append("labour")
    if machines_changed:
        changed.append("machines")
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_OPERATION,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=changed,
        reason=_clean_reason(body.reason),
    )
    db.flush()
    publish("operation.logged", {"db": db, "operation_id": row.id})
    db.commit()
    return _operation_out(db, _operation_or_404(db, user, row.id))


def delete_operation(
    db: Session,
    user: AppUser,
    operation_id: uuid.UUID,
    if_match: str | None,
    reason: str | None = None,
) -> None:
    row = _operation_or_404(db, user, operation_id)
    _require_if_match(row.version, if_match)
    row.version += 1
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_OPERATION,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=["deleted"],
        reason=_clean_reason(reason),
    )
    db.delete(row)
    db.flush()
    publish("operation.logged", {"db": db, "operation_id": operation_id})
    db.commit()


def preview_operation_product(body: OperationProductPreviewIn) -> OperationProductPreviewOut:
    try:
        total = calc.product_total(
            body.rate,
            body.rate_basis.value,  # type: ignore[arg-type]
            body.area_ha,
            body.water_l_ha,
        )
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
    return OperationProductPreviewOut(
        total_qty=total,
        total_unit=body.rate_unit,
        source="calculated",
    )


def _operation_end(row: Operation) -> datetime | None:
    if row.start_at is None:
        return None
    end = _aware(row.start_at)
    if row.duration_min:
        end = end + timedelta(minutes=row.duration_min)
    return end


def _reentry_product_name(row: Operation) -> str:
    """Name of the product that drove the copied safety interval."""
    best_name = ""
    best_phi = -1
    for line in row.products:
        product = line.product
        if product is None:
            continue
        phi = product.preharvest_interval_days
        if phi is not None and phi > best_phi:
            best_phi = phi
            best_name = product.name
    if best_name:
        return best_name
    best_re = -1
    for line in row.products:
        product = line.product
        if product is None or product.reentry_h is None:
            continue
        if product.reentry_h > best_re:
            best_re = product.reentry_h
            best_name = product.name
    if best_name:
        return best_name
    if row.products:
        first = row.products[0].product
        if first is not None:
            return first.name
    return ""


def block_reentry(db: Session, block: Block) -> ReentryOut | None:
    rows = db.scalars(
        select(Operation)
        .options(
            selectinload(Operation.products).selectinload(OperationProduct.product),
            selectinload(Operation.safety),
        )
        .where(Operation.block_id == block.id, Operation.farm_id == block.farm_id)
        .order_by(Operation.date.desc(), Operation.id.desc())
    ).all()
    now = datetime.now(UTC)
    active: ReentryOut | None = None
    for row in rows:
        if row.safety is None or row.safety.reentry_h is None:
            continue
        end = _operation_end(row)
        if end is None:
            continue
        until = end + timedelta(hours=row.safety.reentry_h)
        if now >= until:
            continue
        candidate = ReentryOut(until=until, product=_reentry_product_name(row))
        if active is None or candidate.until > active.until:
            active = candidate
    return active


def _operation_covers_valve(row: Operation, valve_id: uuid.UUID | None) -> bool:
    ids = list(row.valve_ids or [])
    if not ids:
        return True
    if valve_id is None:
        return True
    return valve_id in ids


def preharvest_warning_for(
    db: Session,
    block: Block,
    harvest_date: date,
    valve_id: uuid.UUID | None,
) -> dict[str, object] | None:
    """Most restrictive active PHI spray on the block (valve-aware)."""
    rows = db.scalars(
        select(Operation)
        .options(
            selectinload(Operation.products).selectinload(OperationProduct.product),
            selectinload(Operation.safety),
        )
        .where(
            Operation.block_id == block.id,
            Operation.farm_id == block.farm_id,
            Operation.type.in_(list(_SPRAY_TYPES)),
            Operation.date <= harvest_date,
        )
        .order_by(Operation.date.desc(), Operation.id.desc())
    ).all()
    best: dict[str, object] | None = None
    best_clear: date | None = None
    for row in rows:
        if not _operation_covers_valve(row, valve_id):
            continue
        if row.safety is None or row.safety.preharvest_interval_days is None:
            continue
        phi = row.safety.preharvest_interval_days
        ok, days_since, days_needed = calc.preharvest_ok(harvest_date, row.date, phi)
        if ok:
            continue
        clear_on = row.date + timedelta(days=phi)
        product_name = _reentry_product_name(row)
        candidate = {
            "product": product_name,
            "spray_date": row.date,
            "days_since": days_since,
            "days_needed": days_needed,
        }
        if best is None or (best_clear is not None and clear_on > best_clear):
            best = candidate
            best_clear = clear_on
        elif best_clear is None:
            best = candidate
            best_clear = clear_on
    return best


def _canon_qty(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _unit_label(unit: str) -> str:
    if unit == "l":
        return "L"
    if unit == "ml":
        return "mL"
    return unit


def _operation_title(row: Operation) -> str:
    label = _TYPE_TITLE.get(row.type, row.type.value)
    if not row.products:
        return label
    line = row.products[0]
    product_name = line.product.name if line.product is not None else ""
    rate = _canon_qty(line.rate)
    rate_unit = _unit_label(line.rate_unit.value)
    area = _canon_qty(row.area_ha)
    total = _canon_qty(line.total_qty)
    total_unit = _unit_label(line.total_unit.value)
    rate_part = f"{rate} {rate_unit}/ha"
    if line.rate_basis.value == "per_100l":
        rate_part = f"{rate} {rate_unit} per 100 L"
    elif line.rate_basis.value == "per_block":
        rate_part = f"{rate} {rate_unit}/block"
    return (f"{label} — {product_name} {rate_part} on {area} ha = {total} {total_unit}").strip()


def _operation_details(db: Session, row: Operation) -> str | None:
    parts: list[str] = []
    if row.target:
        parts.append(row.target)
    water = next((line.water_l_ha for line in row.products if line.water_l_ha is not None), None)
    if water is not None:
        m3 = water / Decimal(1000)
        parts.append(f"{_canon_qty(m3)} m³/ha")
    valve_ids = list(row.valve_ids or [])
    if valve_ids:
        names = db.scalars(
            select(Valve.name).where(Valve.id.in_(valve_ids)).order_by(Valve.sort, Valve.name)
        ).all()
        if names:
            parts.append(", ".join(names))
    return " · ".join(parts) if parts else None


def _parse_types(raw: str | None) -> set[str] | None:
    if raw is None or raw.strip() == "":
        return None
    return {part.strip() for part in raw.split(",") if part.strip()}


def _wants(types: set[str] | None, *tokens: str) -> bool:
    if types is None:
        return True
    return any(token in types for token in tokens)


def list_journal(
    db: Session,
    block: Block,
    *,
    date_from: date | None,
    date_to: date | None,
    types: str | None,
) -> JournalListOut:
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    zone = ZoneInfo(farm.timezone)
    wanted = _parse_types(types)
    items: list[JournalItemOut] = []

    if _wants(wanted, "operation", *(op.value for op in OperationType)):
        stmt = (
            select(Operation)
            .options(
                selectinload(Operation.products).selectinload(OperationProduct.product),
            )
            .where(Operation.block_id == block.id, Operation.farm_id == block.farm_id)
        )
        if date_from is not None:
            stmt = stmt.where(Operation.date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Operation.date <= date_to)
        for row in db.scalars(stmt).all():
            if wanted is not None and "operation" not in wanted and row.type.value not in wanted:
                continue
            items.append(
                JournalItemOut(
                    kind=JournalKind.operation,
                    date=row.date,
                    title=_operation_title(row),
                    details=_operation_details(db, row),
                    link_id=row.id,
                    source="calculated",
                    operation_type=row.type,
                    cost_dzd=_operation_cost_dzd(db, row.id),
                    warnings=_operation_warnings(db, row),
                )
            )

    if _wants(wanted, "irrigation"):
        events = db.scalars(
            select(IrrigationEvent).where(
                IrrigationEvent.block_id == block.id,
                IrrigationEvent.farm_id == block.farm_id,
            )
        ).all()
        for event in events:
            local = _aware(event.start_at).astimezone(zone).date()
            if date_from is not None and local < date_from:
                continue
            if date_to is not None and local > date_to:
                continue
            depth = _canon_qty(event.depth_mm)
            volume = _canon_qty(event.volume_m3)
            items.append(
                JournalItemOut(
                    kind=JournalKind.irrigation,
                    date=local,
                    title=f"Irrigation — {depth} mm · {volume} m³",
                    details=f"{event.duration_min} min",
                    link_id=event.id,
                    source=event.source.value,  # type: ignore[arg-type]
                )
            )

    if _wants(wanted, "harvest"):
        entries = db.scalars(
            select(HarvestEntry).where(
                HarvestEntry.block_id == block.id,
                HarvestEntry.farm_id == block.farm_id,
            )
        ).all()
        for entry in entries:
            if date_from is not None and entry.date < date_from:
                continue
            if date_to is not None and entry.date > date_to:
                continue
            qty = _canon_qty(entry.quantity)
            kg = _canon_qty(entry.kg)
            items.append(
                JournalItemOut(
                    kind=JournalKind.harvest,
                    date=entry.date,
                    title=f"Harvest — pass {entry.pass_no}: {qty} {entry.unit.value} = {kg} kg",
                    details=f"{_canon_qty(entry.kg_ha)} kg/ha",
                    link_id=entry.id,
                    source="calculated",
                )
            )

    if _wants(wanted, "stage", "stages"):
        seasons = db.scalars(
            select(BlockSeason).where(
                BlockSeason.block_id == block.id,
                BlockSeason.farm_id == block.farm_id,
            )
        ).all()
        season_ids = [season.id for season in seasons]
        if season_ids:
            observations = db.scalars(
                select(StageObservation).where(StageObservation.block_season_id.in_(season_ids))
            ).all()
            stage_ids = {row.stage_def_id for row in observations}
            stage_rows = {
                row.id: row
                for row in db.scalars(select(StageDef).where(StageDef.id.in_(stage_ids))).all()
            }
            for obs in observations:
                if date_from is not None and obs.observed_on < date_from:
                    continue
                if date_to is not None and obs.observed_on > date_to:
                    continue
                stage = stage_rows.get(obs.stage_def_id)
                name = stage.name_en if stage is not None else obs.stage_def_id.hex
                items.append(
                    JournalItemOut(
                        kind=JournalKind.stage,
                        date=obs.observed_on,
                        title=f"Stage — {name}",
                        details=stage.code if stage is not None else None,
                        link_id=obs.stage_def_id,
                        source="entered",
                    )
                )

    items.sort(key=lambda item: (item.date, str(item.link_id)), reverse=True)
    return JournalListOut(items=items)


def stage_at(db: Session, block: Block, on: date) -> StageAtOut:
    """Observed stage on or before ``on``, else predicted stage for that date."""
    seasons = list(
        db.scalars(
            select(BlockSeason).where(
                BlockSeason.block_id == block.id,
                BlockSeason.farm_id == block.farm_id,
                BlockSeason.year == on.year,
            )
        ).all()
    )
    if not seasons and block.crop_id is not None:
        # Fall back to any season that covers observations around that year.
        seasons = list(
            db.scalars(
                select(BlockSeason).where(
                    BlockSeason.block_id == block.id,
                    BlockSeason.farm_id == block.farm_id,
                )
            ).all()
        )
    if not seasons:
        return StageAtOut(stage=None, date=None, label=None)

    season_ids = [season.id for season in seasons]
    observations = list(
        db.scalars(
            select(StageObservation)
            .where(
                StageObservation.block_season_id.in_(season_ids),
                StageObservation.observed_on <= on,
            )
            .order_by(StageObservation.observed_on.desc(), StageObservation.id.desc())
        ).all()
    )
    stage_ids = {row.stage_def_id for row in observations}
    preds = list(
        db.scalars(
            select(StagePrediction).where(
                StagePrediction.block_season_id.in_(season_ids),
                StagePrediction.predicted_on.is_not(None),
                StagePrediction.predicted_on <= on,
                StagePrediction.label.in_([PredictionLabel.observed, PredictionLabel.predicted]),
            )
        ).all()
    )
    stage_ids.update(row.stage_def_id for row in preds)
    if not stage_ids:
        return StageAtOut(stage=None, date=None, label=None)
    defs = {
        row.id: row for row in db.scalars(select(StageDef).where(StageDef.id.in_(stage_ids))).all()
    }

    def _brief(stage_id: uuid.UUID) -> StageAtBrief | None:
        stage = defs.get(stage_id)
        if stage is None:
            return None
        return StageAtBrief(
            id=stage.id,
            code=stage.code,
            name={"fr": stage.name_fr, "ar": stage.name_ar, "en": stage.name_en},
        )

    if observations:
        # Prefer the observation whose stage has the highest sort among those
        # observed on the latest day; fall back to latest observation alone.
        latest_day = observations[0].observed_on
        same_day = [row for row in observations if row.observed_on == latest_day]
        same_day.sort(
            key=lambda row: defs.get(row.stage_def_id).sort if defs.get(row.stage_def_id) else 0
        )
        chosen = same_day[-1]
        brief = _brief(chosen.stage_def_id)
        if brief is not None:
            return StageAtOut(stage=brief, date=chosen.observed_on, label="observed")

    if preds:
        preds.sort(
            key=lambda row: (
                defs.get(row.stage_def_id).sort if defs.get(row.stage_def_id) else 0,
                row.predicted_on or date.min,
            )
        )
        chosen_pred = preds[-1]
        brief = _brief(chosen_pred.stage_def_id)
        if brief is not None and chosen_pred.predicted_on is not None:
            return StageAtOut(
                stage=brief,
                date=chosen_pred.predicted_on,
                label="predicted",
            )
    return StageAtOut(stage=None, date=None, label=None)
