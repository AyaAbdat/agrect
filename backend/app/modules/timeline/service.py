"""Season timeline for every complete block of a farm, in one request.

The query count is fixed (one query per kind of row, never one per block):
blocks, crops, seasons, confirmed stages, harvest, operations, operation products
and irrigation events.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.catalog.models import Crop, StageDef
from app.modules.farms.models import Farm
from app.modules.harvest.models import HarvestEntry
from app.modules.operations.models import Operation, OperationProduct, Product
from app.modules.phenology.models import BlockSeason, StageObservation
from app.modules.registry.models import Block, BlockStatus
from app.modules.soilwater.models import IrrigationEvent
from app.modules.timeline.schemas import (
    TimelineBlockOut,
    TimelineCropOut,
    TimelineHarvestOut,
    TimelineIrrigationWeekOut,
    TimelineOperationOut,
    TimelineOut,
    TimelineRowOut,
    TimelineStageOut,
)

MAX_RANGE_DAYS = 731


def _names(row: Crop | StageDef) -> dict[str, str]:
    return {"fr": row.name_fr, "ar": row.name_ar, "en": row.name_en}


def _range(farm: Farm, date_from: date | None, date_to: date | None) -> tuple[date, date]:
    year = datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date().year
    start = date_from if date_from is not None else date(year, 1, 1)
    end = date_to if date_to is not None else date(year, 12, 31)
    if end < start:
        raise AppError("validation_error", 422, {"to": "timeline.range_invalid"})
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise AppError("validation_error", 422, {"to": "timeline.range_too_long"})
    return start, end


def _crops(db: Session, blocks: list[Block]) -> dict[uuid.UUID, Crop]:
    ids = {block.crop_id for block in blocks if block.crop_id is not None}
    if not ids:
        return {}
    return {row.id: row for row in db.scalars(select(Crop).where(Crop.id.in_(ids))).all()}


def _season_starts(
    db: Session, block_ids: list[uuid.UUID], start: date, end: date
) -> dict[uuid.UUID, date]:
    """Earliest season start date inside the range, per block."""
    rows = db.execute(
        select(BlockSeason.block_id, BlockSeason.start_date).where(
            BlockSeason.block_id.in_(block_ids),
            BlockSeason.start_date.is_not(None),
            BlockSeason.start_date >= start,
            BlockSeason.start_date <= end,
        )
    ).all()
    found: dict[uuid.UUID, date] = {}
    for block_id, started in rows:
        if block_id not in found or started < found[block_id]:
            found[block_id] = started
    return found


def _stages(
    db: Session, block_ids: list[uuid.UUID], start: date, end: date
) -> dict[uuid.UUID, list[TimelineStageOut]]:
    """Confirmed (observed) stages only; predictions are not part of the timeline."""
    rows = db.execute(
        select(BlockSeason.block_id, StageObservation.observed_on, StageDef)
        .join(BlockSeason, BlockSeason.id == StageObservation.block_season_id)
        .join(StageDef, StageDef.id == StageObservation.stage_def_id)
        .where(
            BlockSeason.block_id.in_(block_ids),
            StageObservation.observed_on >= start,
            StageObservation.observed_on <= end,
        )
        .order_by(StageObservation.observed_on, StageDef.sort)
    ).all()
    found: dict[uuid.UUID, list[TimelineStageOut]] = defaultdict(list)
    for block_id, observed_on, stage in rows:
        found[block_id].append(
            TimelineStageOut(date=observed_on, code=stage.code, names=_names(stage))
        )
    return found


def _harvest(
    db: Session, block_ids: list[uuid.UUID], start: date, end: date
) -> dict[uuid.UUID, list[TimelineHarvestOut]]:
    rows = db.execute(
        select(HarvestEntry.block_id, HarvestEntry.date, HarvestEntry.pass_no, HarvestEntry.kg)
        .where(
            HarvestEntry.block_id.in_(block_ids),
            HarvestEntry.date >= start,
            HarvestEntry.date <= end,
        )
        .order_by(HarvestEntry.date, HarvestEntry.pass_no, HarvestEntry.id)
    ).all()
    found: dict[uuid.UUID, list[TimelineHarvestOut]] = defaultdict(list)
    for block_id, on, pass_no, kg in rows:
        found[block_id].append(TimelineHarvestOut(date=on, pass_no=pass_no, kg=kg))
    return found


def _operations(
    db: Session, block_ids: list[uuid.UUID], start: date, end: date
) -> dict[uuid.UUID, list[TimelineOperationOut]]:
    operations = db.execute(
        select(Operation.id, Operation.block_id, Operation.date, Operation.type)
        .where(
            Operation.block_id.in_(block_ids),
            Operation.date >= start,
            Operation.date <= end,
        )
        .order_by(Operation.date, Operation.id)
    ).all()
    names: dict[uuid.UUID, list[str]] = defaultdict(list)
    if operations:
        product_rows = db.execute(
            select(OperationProduct.operation_id, Product.name)
            .join(Product, Product.id == OperationProduct.product_id)
            .where(OperationProduct.operation_id.in_([row[0] for row in operations]))
            .order_by(OperationProduct.id)
        ).all()
        for operation_id, name in product_rows:
            names[operation_id].append(name)
    found: dict[uuid.UUID, list[TimelineOperationOut]] = defaultdict(list)
    for operation_id, block_id, on, op_type in operations:
        found[block_id].append(
            TimelineOperationOut(date=on, type=op_type, products=names.get(operation_id, []))
        )
    return found


def _irrigation_weeks(
    db: Session, farm: Farm, block_ids: list[uuid.UUID], start: date, end: date
) -> dict[uuid.UUID, list[TimelineIrrigationWeekOut]]:
    """Irrigation events per farm-local week (Monday start), counted per block."""
    zone = ZoneInfo(farm.timezone)
    first = datetime.combine(start, time(0), tzinfo=zone).astimezone(UTC)
    last = datetime.combine(end + timedelta(days=1), time(0), tzinfo=zone).astimezone(UTC)
    starts = db.execute(
        select(IrrigationEvent.block_id, IrrigationEvent.start_at).where(
            IrrigationEvent.block_id.in_(block_ids),
            IrrigationEvent.farm_id == farm.id,
            IrrigationEvent.start_at >= first,
            IrrigationEvent.start_at < last,
        )
    ).all()
    counts: dict[uuid.UUID, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for block_id, started in starts:
        aware = started if started.tzinfo is not None else started.replace(tzinfo=UTC)
        local_day = aware.astimezone(zone).date()
        monday = local_day - timedelta(days=local_day.weekday())
        counts[block_id][monday] += 1
    return {
        block_id: [
            TimelineIrrigationWeekOut(week_start=week, count=count)
            for week, count in sorted(weeks.items())
        ]
        for block_id, weeks in counts.items()
    }


def timeline(db: Session, farm: Farm, date_from: date | None, date_to: date | None) -> TimelineOut:
    start, end = _range(farm, date_from, date_to)
    blocks = list(
        db.scalars(
            select(Block)
            .where(Block.farm_id == farm.id, Block.status == BlockStatus.complete)
            .order_by(Block.name, Block.id)
        ).all()
    )
    if not blocks:
        return TimelineOut(date_from=start, date_to=end, blocks=[])
    ids = [block.id for block in blocks]
    crops = _crops(db, blocks)
    seasons = _season_starts(db, ids, start, end)
    stages = _stages(db, ids, start, end)
    harvest = _harvest(db, ids, start, end)
    operations = _operations(db, ids, start, end)
    irrigation = _irrigation_weeks(db, farm, ids, start, end)
    rows: list[TimelineRowOut] = []
    for block in blocks:
        crop = crops.get(block.crop_id) if block.crop_id is not None else None
        block_harvest = harvest.get(block.id, [])
        rows.append(
            TimelineRowOut(
                block=TimelineBlockOut(id=block.id, name=block.name),
                crop=None if crop is None else TimelineCropOut(code=crop.code, names=_names(crop)),
                season_start=seasons.get(block.id),
                first_harvest_date=min((item.date for item in block_harvest), default=None),
                stages=stages.get(block.id, []),
                harvest=block_harvest,
                operations=operations.get(block.id, []),
                irrigation_weeks=irrigation.get(block.id, []),
            )
        )
    return TimelineOut(date_from=start, date_to=end, blocks=rows)
