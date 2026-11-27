"""Compare one value across every complete block of a farm on one date.

Reads stored rows only (no weather fetch). ``mean_7d`` is computed on the server
over the 7 farm-local days ending at the date, and is null where an average is
not meaningful (cumulative degree days, growth stage).
"""

from __future__ import annotations

import statistics
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.compare.schemas import (
    CompareBlockOut,
    CompareFlagOut,
    CompareMetric,
    CompareOut,
    CompareRowOut,
    Source,
)
from app.modules.farms.models import Farm
from app.modules.operations.service import stage_at
from app.modules.registry.models import Block, BlockStatus
from app.modules.soilwater.models import (
    IrrigationEvent,
    IrrigationSettings,
    IrrigationSource,
    WaterBalanceDaily,
)
from app.modules.weather.service import block_degree_days_at

WINDOW_DAYS = 7
# Same crop and same Kc/efficiency, water left further than this share of TAW from
# the group median -> "same setting, different result".
DRIFT_SHARE_OF_TAW = Decimal("0.25")

_UNITS = {
    CompareMetric.water_left: "mm",
    CompareMetric.water_applied: "mm",
    CompareMetric.crop_water_use: "mm",
    CompareMetric.degree_days: "degc_day",
    CompareMetric.stage: None,
}

Balances = dict[uuid.UUID, dict[date, WaterBalanceDaily]]


def _farm_today(farm: Farm) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date()


def _mean(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal(0)) / Decimal(len(values))


def _water_left(row: WaterBalanceDaily | None) -> Decimal | None:
    """Water left in the root zone = TAW − depletion (mm)."""
    if row is None or row.taw_mm is None or row.depletion_mm is None:
        return None
    return row.taw_mm - row.depletion_mm


def _window(on: date) -> list[date]:
    return [on - timedelta(days=offset) for offset in range(WINDOW_DAYS - 1, -1, -1)]


def _balances(db: Session, block_ids: list[uuid.UUID], on: date) -> Balances:
    found: Balances = defaultdict(dict)
    if not block_ids:
        return found
    rows = db.scalars(
        select(WaterBalanceDaily).where(
            WaterBalanceDaily.block_id.in_(block_ids),
            WaterBalanceDaily.date >= on - timedelta(days=WINDOW_DAYS - 1),
            WaterBalanceDaily.date <= on,
        )
    ).all()
    for row in rows:
        found[row.block_id][row.date] = row
    return found


def _balance_row(block: Block, balances: Balances, on: date, metric: CompareMetric):
    by_day = balances.get(block.id, {})
    pick = _water_left if metric == CompareMetric.water_left else (lambda row: row.etc_mm)
    today = by_day.get(on)
    value = None if today is None else pick(today)
    window = [pick(by_day[day]) for day in _window(on) if day in by_day]
    return value, _mean([item for item in window if item is not None])


def _applied(
    db: Session, farm: Farm, block_ids: list[uuid.UUID], on: date
) -> dict[uuid.UUID, dict[date, list[IrrigationEvent]]]:
    zone = ZoneInfo(farm.timezone)
    first = datetime.combine(on - timedelta(days=WINDOW_DAYS - 1), time(0), tzinfo=zone)
    end = datetime.combine(on + timedelta(days=1), time(0), tzinfo=zone)
    found: dict[uuid.UUID, dict[date, list[IrrigationEvent]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not block_ids:
        return found
    events = db.scalars(
        select(IrrigationEvent).where(
            IrrigationEvent.block_id.in_(block_ids),
            IrrigationEvent.farm_id == farm.id,
            IrrigationEvent.start_at >= first.astimezone(UTC),
            IrrigationEvent.start_at < end.astimezone(UTC),
        )
    ).all()
    for event in events:
        start = event.start_at if event.start_at.tzinfo else event.start_at.replace(tzinfo=UTC)
        found[event.block_id][start.astimezone(zone).date()].append(event)
    return found


def _applied_row(
    by_day: dict[date, list[IrrigationEvent]], on: date
) -> tuple[Decimal, Decimal, Source]:
    """Gross depth applied on the date, and the daily mean over the 7-day window."""
    today = by_day.get(on, [])
    value = sum((event.depth_mm for event in today), Decimal(0))
    total = sum(
        (event.depth_mm for day in _window(on) for event in by_day.get(day, [])), Decimal(0)
    )
    measured = bool(today) and all(event.source == IrrigationSource.measured for event in today)
    return value, total / Decimal(WINDOW_DAYS), "measured" if measured else "calculated"


def _row(
    db: Session,
    farm: Farm,
    block: Block,
    metric: CompareMetric,
    on: date,
    balances: Balances,
    applied: dict[uuid.UUID, dict[date, list[IrrigationEvent]]],
) -> CompareRowOut:
    brief = CompareBlockOut(id=block.id, name=block.name)
    unit = _UNITS[metric]
    if metric in (CompareMetric.water_left, CompareMetric.crop_water_use):
        value, mean = _balance_row(block, balances, on, metric)
        source: Source | None = None if value is None else "calculated"
        return CompareRowOut(block=brief, value=value, unit=unit, mean_7d=mean, source=source)
    if metric == CompareMetric.water_applied:
        depth, mean, source = _applied_row(applied.get(block.id, {}), on)
        return CompareRowOut(block=brief, value=depth, unit=unit, mean_7d=mean, source=source)
    if metric == CompareMetric.degree_days:
        total = block_degree_days_at(db, block, on)
        return CompareRowOut(
            block=brief,
            value=total,
            unit=unit,
            mean_7d=None,
            source=None if total is None else "calculated",
        )
    stage = stage_at(db, block, on)
    if stage.stage is None:
        return CompareRowOut(block=brief, value=None, unit=None, mean_7d=None, source=None)
    return CompareRowOut(
        block=brief,
        value=stage.stage.code,
        value_name=stage.stage.name,
        unit=None,
        mean_7d=None,
        source="entered" if stage.label == "observed" else "calculated",
    )


def _drift_flags(
    db: Session, blocks: list[Block], balances: Balances, on: date
) -> list[CompareFlagOut]:
    """Blocks with the same crop, Kc and efficiency whose water left is far from the median."""
    settings = {
        row.block_id: row
        for row in db.scalars(
            select(IrrigationSettings).where(
                IrrigationSettings.block_id.in_([block.id for block in blocks])
            )
        ).all()
    }
    groups: dict[tuple[uuid.UUID, Decimal, Decimal], list[tuple[uuid.UUID, Decimal, Decimal]]] = (
        defaultdict(list)
    )
    for block in blocks:
        setting = settings.get(block.id)
        row = balances.get(block.id, {}).get(on)
        left = _water_left(row)
        if (
            block.crop_id is None
            or setting is None
            or setting.kc is None
            or setting.efficiency is None
            or left is None
            or row is None
            or row.taw_mm is None
        ):
            continue
        groups[(block.crop_id, setting.kc, setting.efficiency)].append((block.id, left, row.taw_mm))
    flags: list[CompareFlagOut] = []
    for members in groups.values():
        if len(members) < 2:
            continue
        median = statistics.median(left for _id, left, _taw in members)
        drifting = [
            block_id
            for block_id, left, taw in members
            if abs(left - median) > DRIFT_SHARE_OF_TAW * taw
        ]
        if drifting:
            flags.append(CompareFlagOut(block_ids=drifting))
    return flags


def compare(db: Session, farm: Farm, metric: CompareMetric, on: date | None) -> CompareOut:
    day = on if on is not None else _farm_today(farm) - timedelta(days=1)
    if metric == CompareMetric.pest_count:
        return CompareOut(
            metric=metric,
            date=day,
            available=False,
            unavailable_code="compare.metric_unavailable",
            rows=[],
            flags=[],
        )
    blocks = list(
        db.scalars(
            select(Block)
            .where(Block.farm_id == farm.id, Block.status == BlockStatus.complete)
            .order_by(Block.name, Block.id)
        ).all()
    )
    ids = [block.id for block in blocks]
    balances = _balances(db, ids, day)
    applied = _applied(db, farm, ids, day) if metric == CompareMetric.water_applied else {}
    return CompareOut(
        metric=metric,
        date=day,
        available=True,
        rows=[_row(db, farm, block, metric, day, balances, applied) for block in blocks],
        flags=_drift_flags(db, blocks, balances, day),
    )
