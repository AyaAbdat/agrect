"""Harvest entry persistence: convert units/bases, version rows, summaries."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop
from app.modules.farms.models import Farm
from app.modules.harvest import calc
from app.modules.harvest.models import HarvestBasis, HarvestEntry, HarvestQuality, HarvestUnit
from app.modules.harvest.schemas import (
    HarvestBlockSummaryOut,
    HarvestEntryIn,
    HarvestEntryOut,
    HarvestEntryPatch,
    HarvestFarmSummaryOut,
    HarvestFarmTotalsOut,
    HarvestFieldsOut,
    HarvestListOut,
    HarvestPreviewIn,
    HarvestPreviewOut,
    HarvestQualityIn,
    HarvestQualityOut,
    PreharvestWarningOut,
    QualityField,
)
from app.modules.operations.service import preharvest_warning_for
from app.modules.registry.models import Block, Planting, RecordVersion, Valve

_ENTITY = "harvest_entry"

_QUALITY_FIELDS: dict[str, list[QualityField]] = {
    "table_grape": ["brix", "size_grade", "waste_pct"],
    "apple": ["brix", "size_grade", "waste_pct"],
    "olive": ["waste_pct", "moisture_pct"],
    "wheat": ["moisture_pct", "protein_pct", "test_weight_kg_hl"],
    "barley": ["moisture_pct", "protein_pct", "test_weight_kg_hl"],
}

_QUALITY_ATTRS = (
    "brix",
    "size_grade",
    "waste_pct",
    "moisture_pct",
    "protein_pct",
    "test_weight_kg_hl",
)

_ENTRY_FIELDS = (
    "date",
    "pass_no",
    "quantity",
    "unit",
    "unit_weight_kg",
    "basis",
    "valve_id",
    "basis_count",
    "kg",
    "kg_ha",
    "area_ha",
    "inputs_hash",
)


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


def _canon(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _inputs_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _values(row: HarvestEntry, fields: tuple[str, ...]) -> dict[str, object]:
    return {field: getattr(row, field) for field in fields}


def _changed(before: dict[str, object], row: HarvestEntry, fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if getattr(row, field) != before[field]]


def _add_history(
    db: Session,
    row: HarvestEntry,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=row.farm_id,
            entity_type=_ENTITY,
            entity_id=row.id,
            version=row.version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


def _first_planting(db: Session, block: Block) -> Planting | None:
    return db.scalar(
        select(Planting)
        .where(Planting.block_id == block.id, Planting.farm_id == block.farm_id)
        .order_by(Planting.sort, Planting.id)
        .limit(1)
    )


def _valve_or_error(db: Session, block: Block, valve_id: uuid.UUID | None) -> Valve | None:
    if valve_id is None:
        return None
    valve = db.get(Valve, valve_id)
    if valve is None or valve.farm_id != block.farm_id or valve.block_id != block.id:
        raise AppError("validation_error", 422, {"valve_id": "harvest.valve_not_in_block"})
    return valve


def _compute(
    db: Session,
    block: Block,
    *,
    quantity: Decimal,
    unit: HarvestUnit,
    unit_weight_kg: Decimal | None,
    basis: HarvestBasis,
    valve_id: uuid.UUID | None,
    basis_count: Decimal | None,
) -> tuple[Decimal, Decimal, Decimal, str, Valve | None]:
    valve = _valve_or_error(db, block, valve_id) if basis == HarvestBasis.valve else None
    if basis == HarvestBasis.valve and valve is None:
        raise AppError("validation_error", 422, {"valve_id": "harvest.valve_required"})
    planting = _first_planting(db, block)
    trees_per_ha = None if planting is None else planting.trees_per_ha
    net_area = block.net_area_ha
    if net_area is None:
        raise AppError("validation_error", 422, {"net_area_ha": "harvest.net_area_required"})
    rows_total = None if block.rows_total is None else Decimal(block.rows_total)
    valve_area = None if valve is None else valve.area_ha
    try:
        kg = calc.harvest_kg(quantity, unit.value, unit_weight_kg)  # type: ignore[arg-type]
        area = calc.basis_area_ha(
            basis.value,  # type: ignore[arg-type]
            net_area_ha=net_area,
            valve_area_ha=valve_area,
            rows_picked=basis_count if basis == HarvestBasis.rows else None,
            rows_total=rows_total if basis == HarvestBasis.rows else None,
            trees_picked=basis_count if basis == HarvestBasis.trees else None,
            trees_per_ha=trees_per_ha if basis == HarvestBasis.trees else None,
        )
        density = calc.kg_per_ha(kg, area)
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
    digest = _inputs_hash(
        {
            "quantity": _canon(quantity),
            "unit": unit.value,
            "unit_weight_kg": _canon(unit_weight_kg),
            "basis": basis.value,
            "valve_id": None if valve is None else str(valve.id),
            "basis_count": _canon(basis_count),
            "net_area_ha": _canon(net_area),
            "valve_area_ha": _canon(valve_area),
            "rows_total": None if rows_total is None else _canon(rows_total),
            "trees_per_ha": trees_per_ha,
        }
    )
    return kg, area, density, digest, valve


def _quality_out(row: HarvestQuality | None) -> HarvestQualityOut | None:
    if row is None:
        return None
    return HarvestQualityOut(
        brix=row.brix,
        size_grade=row.size_grade,
        waste_pct=row.waste_pct,
        moisture_pct=row.moisture_pct,
        protein_pct=row.protein_pct,
        test_weight_kg_hl=row.test_weight_kg_hl,
    )


def _warning_out(
    db: Session,
    block: Block,
    harvest_date: date,
    valve_id: uuid.UUID | None,
) -> PreharvestWarningOut | None:
    raw = preharvest_warning_for(db, block, harvest_date, valve_id)
    if raw is None:
        return None
    return PreharvestWarningOut(
        product=str(raw["product"]),
        spray_date=raw["spray_date"],  # type: ignore[arg-type]
        days_since=int(raw["days_since"]),  # type: ignore[arg-type]
        days_needed=int(raw["days_needed"]),  # type: ignore[arg-type]
    )


def _entry_out(db: Session, block: Block, row: HarvestEntry) -> HarvestEntryOut:
    return HarvestEntryOut(
        id=row.id,
        block_id=row.block_id,
        valve_id=row.valve_id,
        date=row.date,
        pass_no=row.pass_no,
        quantity=row.quantity,
        unit=row.unit,
        unit_weight_kg=row.unit_weight_kg,
        basis=row.basis,
        basis_count=row.basis_count,
        kg=row.kg,
        kg_ha=row.kg_ha,
        area_ha=row.area_ha,
        source="calculated",
        quality=_quality_out(row.quality),
        preharvest_warning=_warning_out(db, block, row.date, row.valve_id),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _validate_size_grade(size_grade: dict[str, object] | None) -> None:
    """Each grade share is 0–100 and the shares sum to at most 100."""
    if size_grade is None:
        return
    total = Decimal(0)
    for value in size_grade.values():
        try:
            parsed = value if isinstance(value, Decimal) else Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            raise AppError(
                "validation_error",
                422,
                {"size_grade": "harvest.size_grade_sum_invalid"},
            ) from None
        if not parsed.is_finite() or parsed < 0 or parsed > 100:
            raise AppError(
                "validation_error",
                422,
                {"size_grade": "harvest.size_grade_sum_invalid"},
            )
        total += parsed
    if total > 100:
        raise AppError(
            "validation_error",
            422,
            {"size_grade": "harvest.size_grade_sum_invalid"},
        )


def _apply_quality(row: HarvestEntry, body: HarvestQualityIn | None) -> bool:
    """Create/update/clear quality. Returns True when quality fields changed."""
    if body is None:
        return False
    _validate_size_grade(body.size_grade)
    values = {name: getattr(body, name) for name in _QUALITY_ATTRS}
    if all(value is None for value in values.values()):
        if row.quality is not None:
            row.quality = None
            return True
        return False
    if row.quality is None:
        row.quality = HarvestQuality(harvest_entry_id=row.id)
        changed = True
    else:
        changed = False
    quality = row.quality
    for name, value in values.items():
        if getattr(quality, name) != value:
            setattr(quality, name, value)
            changed = True
    return changed


def _entry_or_404(db: Session, block: Block, entry_id: uuid.UUID) -> HarvestEntry:
    row = db.scalar(
        select(HarvestEntry)
        .options(selectinload(HarvestEntry.quality))
        .where(
            HarvestEntry.id == entry_id,
            HarvestEntry.block_id == block.id,
            HarvestEntry.farm_id == block.farm_id,
        )
    )
    if row is None:
        raise AppError("harvest.not_found", 404)
    return row


def list_entries(db: Session, block: Block) -> HarvestListOut:
    rows = db.scalars(
        select(HarvestEntry)
        .options(selectinload(HarvestEntry.quality))
        .where(
            HarvestEntry.block_id == block.id,
            HarvestEntry.farm_id == block.farm_id,
        )
        .order_by(HarvestEntry.date.desc(), HarvestEntry.pass_no.desc(), HarvestEntry.id.desc())
    ).all()
    return HarvestListOut(entries=[_entry_out(db, block, row) for row in rows])


def create_entry(
    db: Session,
    block: Block,
    user: AppUser,
    body: HarvestEntryIn,
) -> HarvestEntryOut:
    kg, area, density, digest, valve = _compute(
        db,
        block,
        quantity=body.quantity,
        unit=body.unit,
        unit_weight_kg=body.unit_weight_kg,
        basis=body.basis,
        valve_id=body.valve_id,
        basis_count=body.basis_count,
    )
    now = datetime.now(UTC)
    row = HarvestEntry(
        farm_id=block.farm_id,
        block_id=block.id,
        valve_id=None if valve is None else valve.id,
        date=body.date,
        pass_no=body.pass_no,
        quantity=body.quantity,
        unit=body.unit,
        unit_weight_kg=body.unit_weight_kg,
        basis=body.basis,
        basis_count=body.basis_count,
        kg=kg,
        kg_ha=density,
        area_ha=area,
        inputs_hash=digest,
        user_id=user.id,
        version=1,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    _apply_quality(row, body.quality)
    _add_history(db, row, user, list(_ENTRY_FIELDS) + (["quality"] if body.quality else []), None)
    db.commit()
    db.refresh(row)
    return _entry_out(db, block, _entry_or_404(db, block, row.id))


def update_entry(
    db: Session,
    block: Block,
    user: AppUser,
    entry_id: uuid.UUID,
    body: HarvestEntryPatch,
    if_match: str | None,
) -> HarvestEntryOut:
    row = _entry_or_404(db, block, entry_id)
    _require_if_match(row.version, if_match)
    before = _values(row, _ENTRY_FIELDS)
    quantity = row.quantity if body.quantity is None else body.quantity
    unit = row.unit if body.unit is None else body.unit
    unit_weight = row.unit_weight_kg if body.unit_weight_kg is None else body.unit_weight_kg
    basis = row.basis if body.basis is None else body.basis
    basis_count = row.basis_count if body.basis_count is None else body.basis_count
    if "valve_id" in body.model_fields_set:
        valve_id = body.valve_id
    elif body.basis is not None and body.basis != HarvestBasis.valve:
        valve_id = None
    else:
        valve_id = row.valve_id
    if body.date is not None:
        row.date = body.date
    if body.pass_no is not None:
        row.pass_no = body.pass_no
    kg, area, density, digest, valve = _compute(
        db,
        block,
        quantity=quantity,
        unit=unit,
        unit_weight_kg=unit_weight,
        basis=basis,
        valve_id=valve_id,
        basis_count=basis_count,
    )
    row.quantity = quantity
    row.unit = unit
    row.unit_weight_kg = unit_weight
    row.basis = basis
    row.valve_id = None if valve is None else valve.id
    row.basis_count = basis_count
    row.kg = kg
    row.kg_ha = density
    row.area_ha = area
    row.inputs_hash = digest
    quality_changed = _apply_quality(row, body.quality)
    changed = _changed(before, row, _ENTRY_FIELDS)
    if quality_changed:
        changed.append("quality")
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(db, row, user, changed, _clean_reason(body.reason))
    db.commit()
    return _entry_out(db, block, _entry_or_404(db, block, row.id))


def delete_entry(
    db: Session,
    block: Block,
    user: AppUser,
    entry_id: uuid.UUID,
    if_match: str | None,
    reason: str | None = None,
) -> None:
    row = _entry_or_404(db, block, entry_id)
    _require_if_match(row.version, if_match)
    row.version += 1
    _add_history(db, row, user, ["deleted"], _clean_reason(reason))
    db.delete(row)
    db.commit()


def preview_harvest(db: Session, user: AppUser, body: HarvestPreviewIn) -> HarvestPreviewOut:
    block = db.get(Block, body.block_id)
    if block is None or block.farm.owner_user_id != user.id:
        raise AppError("block.not_found", 404)
    kg, area, density, _digest, _valve = _compute(
        db,
        block,
        quantity=body.quantity,
        unit=body.unit,
        unit_weight_kg=body.unit_weight_kg,
        basis=body.basis,
        valve_id=body.valve_id,
        basis_count=body.basis_count,
    )
    return HarvestPreviewOut(kg=kg, kg_ha=density, area_ha=area, source="calculated")


def harvest_fields(db: Session, crop_id: uuid.UUID) -> HarvestFieldsOut:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise AppError("catalog.crop_not_found", 404)
    fields = _QUALITY_FIELDS.get(crop.code, [])
    return HarvestFieldsOut(crop_id=crop.id, crop_code=crop.code, fields=fields)


def farm_summary(db: Session, farm: Farm, season: int) -> HarvestFarmSummaryOut:
    if season < 1:
        raise AppError("validation_error", 422, {"season": "harvest.season_invalid"})
    start = datetime(season, 1, 1, tzinfo=UTC).date()
    end = datetime(season, 12, 31, tzinfo=UTC).date()
    blocks = list(
        db.scalars(
            select(Block).where(Block.farm_id == farm.id).order_by(Block.name, Block.id)
        ).all()
    )
    entries = list(
        db.scalars(
            select(HarvestEntry).where(
                HarvestEntry.farm_id == farm.id,
                HarvestEntry.date >= start,
                HarvestEntry.date <= end,
            )
        ).all()
    )
    by_block: dict[uuid.UUID, list[HarvestEntry]] = {block.id: [] for block in blocks}
    for entry in entries:
        by_block.setdefault(entry.block_id, []).append(entry)
    block_summaries: list[HarvestBlockSummaryOut] = []
    farm_kg = Decimal(0)
    harvested_area = Decimal(0)
    blocks_harvested = 0
    for block in blocks:
        rows = by_block.get(block.id, [])
        kg_total = sum((row.kg for row in rows), Decimal(0))
        farm_kg += kg_total
        passes = len({(row.date, row.pass_no) for row in rows})
        kg_ha = None
        if block.net_area_ha is not None and block.net_area_ha > 0 and rows:
            kg_ha = kg_total / block.net_area_ha
            harvested_area += block.net_area_ha
            blocks_harvested += 1
        elif rows:
            blocks_harvested += 1
        block_summaries.append(
            HarvestBlockSummaryOut(
                block_id=block.id,
                kg_total=kg_total,
                kg_ha=kg_ha,
                passes=passes,
            )
        )
    farm_kg_ha = None
    if harvested_area > 0:
        farm_kg_ha = farm_kg / harvested_area
    return HarvestFarmSummaryOut(
        season=season,
        farm=HarvestFarmTotalsOut(
            kg_total=farm_kg,
            kg_ha=farm_kg_ha,
            blocks_harvested=blocks_harvested,
        ),
        blocks=block_summaries,
    )
