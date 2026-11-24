"""Farm station, pumps, water sources, and the capacity check.

The shift plan is a planning aid. A stored capacity decision does not change irrigation.
"""

import enum
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from app.modules.registry.models import Block, BlockStatus, IrrigationLayout, Valve
from app.modules.soilwater import calc as soil_calc
from app.modules.soilwater.models import IrrigationSettings
from app.modules.soilwater.service import read_irrigation_today
from app.modules.station import calc
from app.modules.station.models import (
    CapacityDecision,
    CapacityMode,
    Pump,
    PumpBlock,
    PumpWindow,
    Station,
    WaterSource,
)
from app.modules.station.schemas import (
    BlocksPut,
    CapacityCheckOut,
    CapacityDecisionIn,
    CapacityDecisionOut,
    CapacitySummaryOut,
    FarmStationOut,
    PumpBlockOut,
    PumpIn,
    PumpOut,
    PumpPatch,
    PumpWindowOut,
    ShiftOut,
    StationOut,
    StationTotals,
    ValveFlowOut,
    WaterSourceIn,
    WaterSourceOut,
    WaterSourcePatch,
    WindowsPut,
)
from app.modules.weather.models import WeatherDaily

_NAME_MAX = 255


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


def _clean_name(name: str | None) -> str:
    if name is None:
        return ""
    return name.strip()


def _name_error(name: str) -> dict[str, str]:
    if name == "" or len(name) > _NAME_MAX:
        return {"name": "station.name_required"}
    return {}


def _flow_error(flow: Decimal | None) -> dict[str, str]:
    if flow is None or not flow.is_finite() or flow <= 0:
        return {"flow_m3h": "station.flow_must_be_positive"}
    return {}


def _clock(value: str) -> time:
    try:
        parsed = time.fromisoformat(value.strip())
    except ValueError:
        raise AppError("validation_error", 422, {"windows": "station.window_invalid"}) from None
    if parsed.tzinfo is not None:
        raise AppError("validation_error", 422, {"windows": "station.window_invalid"})
    return parsed


def _unique_ids(block_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    seen: set[uuid.UUID] = set()
    ordered: list[uuid.UUID] = []
    for block_id in block_ids:
        if block_id in seen:
            continue
        seen.add(block_id)
        ordered.append(block_id)
    return ordered


def _require_blocks(db: Session, farm_id: uuid.UUID, block_ids: list[uuid.UUID]) -> None:
    if not block_ids:
        return
    found = set(
        db.scalars(select(Block.id).where(Block.farm_id == farm_id, Block.id.in_(block_ids))).all()
    )
    if found != set(block_ids):
        raise AppError("validation_error", 422, {"block_ids": "station.block_not_in_farm"})


def _require_source(db: Session, farm_id: uuid.UUID, source_id: uuid.UUID | None) -> None:
    if source_id is None:
        return
    row = db.get(WaterSource, source_id)
    if row is None or row.farm_id != farm_id:
        raise AppError(
            "validation_error",
            422,
            {"water_source_id": "station.water_source_not_found"},
        )


def _name_taken(db: Session, station_id: uuid.UUID, name: str, pump_id: uuid.UUID | None) -> bool:
    stmt = select(Pump.id).where(Pump.station_id == station_id, Pump.name == name)
    if pump_id is not None:
        stmt = stmt.where(Pump.id != pump_id)
    return db.scalar(stmt.limit(1)) is not None


def _station_row(db: Session, farm_id: uuid.UUID) -> Station | None:
    return db.scalar(select(Station).where(Station.farm_id == farm_id))


def _ensure_station(db: Session, farm: Farm) -> Station:
    row = _station_row(db, farm.id)
    if row is not None:
        return row
    now = datetime.now(UTC)
    row = Station(farm_id=farm.id, name="Station", version=1, updated_at=now)
    db.add(row)
    db.flush()
    return row


def _owned_pump(db: Session, user: AppUser, pump_id: uuid.UUID) -> Pump:
    pump = db.get(Pump, pump_id)
    if pump is None:
        raise AppError("pump.not_found", 404)
    farm = db.get(Farm, pump.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("pump.not_found", 404)
    return pump


def _owned_source(db: Session, user: AppUser, source_id: uuid.UUID) -> WaterSource:
    row = db.get(WaterSource, source_id)
    if row is None:
        raise AppError("water_source.not_found", 404)
    farm = db.get(Farm, row.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("water_source.not_found", 404)
    return row


def _source_out(row: WaterSource) -> WaterSourceOut:
    return WaterSourceOut(
        id=row.id,
        name=row.name,
        kind=row.kind,
        ec_ds_m=row.ec_ds_m,
        basin_volume_m3=row.basin_volume_m3,
    )


def _sources(db: Session, farm_id: uuid.UUID) -> list[WaterSource]:
    return list(
        db.scalars(
            select(WaterSource)
            .where(WaterSource.farm_id == farm_id)
            .order_by(WaterSource.name, WaterSource.id)
        ).all()
    )


def _pumps(db: Session, farm_id: uuid.UUID) -> list[Pump]:
    return list(
        db.scalars(select(Pump).where(Pump.farm_id == farm_id).order_by(Pump.name, Pump.id)).all()
    )


def _windows_by_pump(db: Session, pump_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[PumpWindow]]:
    grouped: dict[uuid.UUID, list[PumpWindow]] = {pump_id: [] for pump_id in pump_ids}
    if not pump_ids:
        return grouped
    rows = db.scalars(
        select(PumpWindow)
        .where(PumpWindow.pump_id.in_(pump_ids))
        .order_by(PumpWindow.start_time, PumpWindow.id)
    ).all()
    for row in rows:
        grouped.setdefault(row.pump_id, []).append(row)
    return grouped


def _blocks_by_pump(
    db: Session,
    pump_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[PumpBlockOut]]:
    grouped: dict[uuid.UUID, list[PumpBlockOut]] = {pump_id: [] for pump_id in pump_ids}
    if not pump_ids:
        return grouped
    rows = db.execute(
        select(PumpBlock.pump_id, Block.id, Block.name)
        .join(Block, Block.id == PumpBlock.block_id)
        .where(PumpBlock.pump_id.in_(pump_ids))
        .order_by(Block.name, Block.id)
    ).all()
    for pump_id, block_id, name in rows:
        grouped.setdefault(pump_id, []).append(PumpBlockOut(id=block_id, name=name))
    return grouped


def _pump_out(
    pump: Pump,
    blocks: list[PumpBlockOut],
    windows: list[PumpWindow],
    source: WaterSource | None,
) -> PumpOut:
    return PumpOut(
        id=pump.id,
        name=pump.name,
        flow_m3h=pump.flow_m3h,
        serves_all_blocks=pump.serves_all_blocks,
        pressure_bar=pump.pressure_bar,
        version=pump.version,
        blocks=blocks,
        windows=[
            PumpWindowOut(id=row.id, start_time=row.start_time, end_time=row.end_time)
            for row in windows
        ],
        water_source=None if source is None else _source_out(source),
    )


def _pump_views(db: Session, pumps: list[Pump]) -> list[PumpOut]:
    pump_ids = [pump.id for pump in pumps]
    blocks = _blocks_by_pump(db, pump_ids)
    windows = _windows_by_pump(db, pump_ids)
    source_ids = {pump.water_source_id for pump in pumps if pump.water_source_id is not None}
    sources = (
        {
            row.id: row
            for row in db.scalars(select(WaterSource).where(WaterSource.id.in_(source_ids))).all()
        }
        if source_ids
        else {}
    )
    return [
        _pump_out(
            pump,
            blocks.get(pump.id, []),
            windows.get(pump.id, []),
            None if pump.water_source_id is None else sources.get(pump.water_source_id),
        )
        for pump in pumps
    ]


def _one_pump(db: Session, pump: Pump) -> PumpOut:
    return _pump_views(db, [pump])[0]


def read_station(db: Session, farm: Farm) -> FarmStationOut:
    station = _station_row(db, farm.id)
    pumps = _pumps(db, farm.id)
    sources = _sources(db, farm.id)
    total = sum((pump.flow_m3h for pump in pumps), Decimal(0))
    return FarmStationOut(
        station=None
        if station is None
        else StationOut(
            id=station.id,
            name=station.name,
            version=station.version,
            created_at=station.created_at,
            updated_at=station.updated_at,
        ),
        pumps=_pump_views(db, pumps),
        water_sources=[_source_out(row) for row in sources],
        totals=StationTotals(pumps_flow_m3h=total),
    )


def _replace_block_links(db: Session, pump: Pump, block_ids: list[uuid.UUID]) -> None:
    db.execute(delete(PumpBlock).where(PumpBlock.pump_id == pump.id))
    for block_id in block_ids:
        db.add(PumpBlock(pump_id=pump.id, block_id=block_id, farm_id=pump.farm_id))


def create_pump(db: Session, farm: Farm, body: PumpIn) -> PumpOut:
    name = _clean_name(body.name)
    errors = _name_error(name)
    errors.update(_flow_error(body.flow_m3h))
    if errors:
        raise AppError("validation_error", 422, errors)
    _require_source(db, farm.id, body.water_source_id)
    block_ids = [] if body.block_ids is None else _unique_ids(body.block_ids)
    serves_all = body.serves_all_blocks
    if not serves_all:
        _require_blocks(db, farm.id, block_ids)
    station = _ensure_station(db, farm)
    if _name_taken(db, station.id, name, None):
        raise AppError("validation_error", 422, {"name": "station.name_taken"})
    pump = Pump(
        farm_id=farm.id,
        station_id=station.id,
        name=name,
        flow_m3h=body.flow_m3h,
        serves_all_blocks=serves_all,
        pressure_bar=body.pressure_bar,
        water_source_id=body.water_source_id,
        version=1,
    )
    db.add(pump)
    db.flush()
    if not serves_all:
        _replace_block_links(db, pump, block_ids)
    db.commit()
    db.refresh(pump)
    return _one_pump(db, pump)


def update_pump(
    db: Session,
    user: AppUser,
    pump_id: uuid.UUID,
    body: PumpPatch,
    if_match: str | None,
) -> PumpOut:
    pump = _owned_pump(db, user, pump_id)
    _require_if_match(pump.version, if_match)
    provided = body.model_fields_set
    errors: dict[str, str] = {}
    name = pump.name
    if "name" in provided:
        name = _clean_name(body.name)
        errors.update(_name_error(name))
    flow = pump.flow_m3h
    if "flow_m3h" in provided:
        flow = body.flow_m3h
        errors.update(_flow_error(flow))
    if errors:
        raise AppError("validation_error", 422, errors)
    if "water_source_id" in provided:
        _require_source(db, pump.farm_id, body.water_source_id)
    if name != pump.name and _name_taken(db, pump.station_id, name, pump.id):
        raise AppError("validation_error", 422, {"name": "station.name_taken"})
    pump.name = name
    if flow is not None:
        pump.flow_m3h = flow
    if "pressure_bar" in provided:
        pump.pressure_bar = body.pressure_bar
    if "water_source_id" in provided:
        pump.water_source_id = body.water_source_id
    if "serves_all_blocks" in provided and body.serves_all_blocks is not None:
        pump.serves_all_blocks = body.serves_all_blocks
        if body.serves_all_blocks:
            db.execute(delete(PumpBlock).where(PumpBlock.pump_id == pump.id))
    pump.version += 1
    db.commit()
    db.refresh(pump)
    return _one_pump(db, pump)


def delete_pump(db: Session, user: AppUser, pump_id: uuid.UUID, if_match: str | None) -> None:
    pump = _owned_pump(db, user, pump_id)
    _require_if_match(pump.version, if_match)
    db.execute(delete(PumpWindow).where(PumpWindow.pump_id == pump.id))
    db.execute(delete(PumpBlock).where(PumpBlock.pump_id == pump.id))
    db.delete(pump)
    db.commit()


def replace_windows(
    db: Session,
    user: AppUser,
    pump_id: uuid.UUID,
    body: WindowsPut,
    if_match: str | None,
) -> PumpOut:
    pump = _owned_pump(db, user, pump_id)
    _require_if_match(pump.version, if_match)
    clocks = [(_clock(window.start_time), _clock(window.end_time)) for window in body.windows]
    db.execute(delete(PumpWindow).where(PumpWindow.pump_id == pump.id))
    for start, end in clocks:
        db.add(
            PumpWindow(
                farm_id=pump.farm_id,
                pump_id=pump.id,
                start_time=start,
                end_time=end,
            )
        )
    pump.version += 1
    db.commit()
    db.refresh(pump)
    return _one_pump(db, pump)


def replace_blocks(
    db: Session,
    user: AppUser,
    pump_id: uuid.UUID,
    body: BlocksPut,
    if_match: str | None,
) -> PumpOut:
    pump = _owned_pump(db, user, pump_id)
    _require_if_match(pump.version, if_match)
    block_ids = _unique_ids(body.block_ids)
    _require_blocks(db, pump.farm_id, block_ids)
    pump.serves_all_blocks = False
    _replace_block_links(db, pump, block_ids)
    pump.version += 1
    db.commit()
    db.refresh(pump)
    return _one_pump(db, pump)


def list_water_sources(db: Session, farm: Farm) -> list[WaterSourceOut]:
    return [_source_out(row) for row in _sources(db, farm.id)]


def create_water_source(db: Session, farm: Farm, body: WaterSourceIn) -> WaterSourceOut:
    name = _clean_name(body.name)
    errors = _name_error(name)
    if errors:
        raise AppError("validation_error", 422, errors)
    row = WaterSource(
        farm_id=farm.id,
        name=name,
        kind=body.kind,
        ec_ds_m=body.ec_ds_m,
        basin_volume_m3=body.basin_volume_m3,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _source_out(row)


def update_water_source(
    db: Session,
    user: AppUser,
    source_id: uuid.UUID,
    body: WaterSourcePatch,
) -> WaterSourceOut:
    row = _owned_source(db, user, source_id)
    provided = body.model_fields_set
    if "name" in provided:
        name = _clean_name(body.name)
        errors = _name_error(name)
        if errors:
            raise AppError("validation_error", 422, errors)
        row.name = name
    if "kind" in provided and body.kind is not None:
        row.kind = body.kind
    if "ec_ds_m" in provided:
        row.ec_ds_m = body.ec_ds_m
    if "basin_volume_m3" in provided:
        row.basin_volume_m3 = body.basin_volume_m3
    db.commit()
    db.refresh(row)
    return _source_out(row)


def delete_water_source(db: Session, user: AppUser, source_id: uuid.UUID) -> None:
    row = _owned_source(db, user, source_id)
    db.delete(row)
    db.commit()


def _farm_today(farm: Farm) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date()


def _today_run_time(db: Session, block: Block) -> tuple[Decimal, bool]:
    advice = read_irrigation_today(db, block)
    dose = advice.refill if advice.recommended == "refill" else advice.maintain
    if dose.run_time_min is None:
        return Decimal(0), False
    return dose.run_time_min, True


def _usable_positive(value: Decimal | None) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value > 0


def _usable_efficiency(value: Decimal | None) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and Decimal(0) < value <= 1


def _peak_et0(db: Session, farm: Farm, today: date) -> list[Decimal | None]:
    """ET0 on the last 7 calendar days and the next 7, by stored vs forecast.

    Stored days are today−6 through today when ``is_forecast`` is false.
    Forecast days are today through today+6 when ``is_forecast`` is true.
    Today sits in whichever bucket its row uses.
    """
    stored_from = today - timedelta(days=6)
    forecast_to = today + timedelta(days=6)
    stored = db.scalars(
        select(WeatherDaily)
        .where(
            WeatherDaily.farm_id == farm.id,
            WeatherDaily.is_forecast.is_(False),
            WeatherDaily.date >= stored_from,
            WeatherDaily.date <= today,
        )
        .order_by(WeatherDaily.date)
    ).all()
    forecast = db.scalars(
        select(WeatherDaily)
        .where(
            WeatherDaily.farm_id == farm.id,
            WeatherDaily.is_forecast.is_(True),
            WeatherDaily.date >= today,
            WeatherDaily.date <= forecast_to,
        )
        .order_by(WeatherDaily.date)
    ).all()
    return [row.et0_mm for row in (*stored, *forecast)]


def _peak_run_time(
    et0_values: list[Decimal | None],
    kc: Decimal | None,
    efficiency: Decimal | None,
    rate_mm_h: Decimal | None,
) -> tuple[Decimal, bool]:
    """Largest daily gross need in the peak week, as minutes at the block rate.

    gross_mm = ETc / efficiency, with ETc = ET0 × Kc. Minutes = gross / rate × 60.
    A block missing Kc, efficiency, rate, or any ET0 in the week has no dose.
    """
    if kc is None or efficiency is None or rate_mm_h is None:
        return Decimal(0), False
    if (
        not _usable_positive(kc)
        or not _usable_efficiency(efficiency)
        or not _usable_positive(rate_mm_h)
    ):
        return Decimal(0), False
    best = Decimal(0)
    saw_day = False
    for et0 in et0_values:
        if not isinstance(et0, Decimal) or not et0.is_finite():
            continue
        saw_day = True
        if et0 <= 0:
            continue
        try:
            etc = soil_calc.etc_mm(et0, kc)
            gross = soil_calc.gross_mm(etc, efficiency)
            minutes = soil_calc.run_time_min(gross, rate_mm_h)
        except soil_calc.CalcInputError:
            continue
        if minutes > best:
            best = minutes
    if not saw_day:
        return Decimal(0), False
    return best, True


def _block_inputs(
    db: Session,
    block: Block,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    settings = db.scalar(
        select(IrrigationSettings).where(
            IrrigationSettings.block_id == block.id,
            IrrigationSettings.farm_id == block.farm_id,
        )
    )
    layout = db.scalar(
        select(IrrigationLayout).where(
            IrrigationLayout.block_id == block.id,
            IrrigationLayout.farm_id == block.farm_id,
        )
    )
    kc = None if settings is None else settings.kc
    efficiency = None if settings is None else settings.efficiency
    rate = None if layout is None else layout.rate_mm_h
    return kc, efficiency, rate


def _run_times(
    db: Session,
    farm: Farm,
    blocks: list[Block],
    mode: CapacityMode,
) -> tuple[dict[uuid.UUID, Decimal], list[uuid.UUID]]:
    times: dict[uuid.UUID, Decimal] = {}
    missing: list[uuid.UUID] = []
    et0_values = _peak_et0(db, farm, _farm_today(farm)) if mode == CapacityMode.peak_week else []
    for block in blocks:
        if mode == CapacityMode.today:
            minutes, ready = _today_run_time(db, block)
        else:
            kc, efficiency, rate = _block_inputs(db, block)
            minutes, ready = _peak_run_time(et0_values, kc, efficiency, rate)
        times[block.id] = minutes
        if not ready:
            missing.append(block.id)
    return times, missing


def _demands(
    db: Session,
    farm: Farm,
    blocks: list[Block],
    run_times: dict[uuid.UUID, Decimal],
) -> list[calc.ValveDemand]:
    if not blocks:
        return []
    rows = db.scalars(
        select(Valve)
        .where(
            Valve.farm_id == farm.id,
            Valve.block_id.in_([block.id for block in blocks]),
            Valve.q_m3h.is_not(None),
            Valve.q_m3h > 0,
        )
        .order_by(Valve.block_id, Valve.sort, Valve.id)
    ).all()
    demands: list[calc.ValveDemand] = []
    for valve in rows:
        flow = valve.q_m3h
        if flow is None or flow <= 0:
            continue
        demands.append((valve.id, valve.block_id, flow, run_times[valve.block_id]))
    return demands


def _pump_hours(db: Session, farm: Farm) -> list[calc.PumpHours]:
    pumps = _pumps(db, farm.id)
    if not pumps:
        return []
    pump_ids = [pump.id for pump in pumps]
    link_rows = db.scalars(select(PumpBlock).where(PumpBlock.pump_id.in_(pump_ids))).all()
    by_pump: dict[uuid.UUID, set[uuid.UUID]] = {pump.id: set() for pump in pumps}
    for link in link_rows:
        by_pump.setdefault(link.pump_id, set()).add(link.block_id)
    windows = _windows_by_pump(db, pump_ids)
    supplies: list[calc.PumpHours] = []
    for pump in pumps:
        scope: calc.PumpScope = (
            calc.ALL if pump.serves_all_blocks else frozenset(by_pump.get(pump.id, set()))
        )
        clocks = tuple((row.start_time, row.end_time) for row in windows.get(pump.id, []))
        supplies.append((pump.id, pump.flow_m3h, scope, clocks))
    return supplies


def _valve_out(valve: calc.ShiftValve) -> ValveFlowOut:
    return ValveFlowOut(
        valve_id=valve.valve_id,
        block_id=valve.block_id,
        q_m3h=valve.q_m3h,
        run_time_min=valve.run_time_min,
    )


def _check_out(
    mode: CapacityMode,
    result: calc.CapacitySummary,
    plan: calc.ShiftPlan,
    no_dose_blocks: list[uuid.UUID],
) -> CapacityCheckOut:
    return CapacityCheckOut(
        mode=mode,
        source="calculated",
        summary=CapacitySummaryOut(
            open_together_flow_m3h=result.open_together_flow_m3h,
            pumps_flow_m3h=result.pumps_flow_m3h,
            short_by_m3h=result.short_by_m3h,
            hours_needed=result.hours_needed,
            hours_available=result.hours_available,
            fits_in_hours=result.fits_in_hours,
        ),
        shifts=[
            ShiftOut(
                valves=[_valve_out(valve) for valve in shift.valves],
                flow_m3h=shift.flow_m3h,
                time_min=shift.time_min,
            )
            for shift in plan.shifts
        ],
        cannot_supply=[_valve_out(valve) for valve in plan.cannot_supply],
        no_dose_blocks=no_dose_blocks,
    )


def read_capacity_check(db: Session, farm: Farm, mode: CapacityMode) -> CapacityCheckOut:
    """Open valves of complete blocks against the station's pumps.

    ``today`` uses the recommended irrigation-today run time. ``peak_week`` uses
    the largest daily gross need (ETc / efficiency) over the last 7 stored days
    and the 7 forecast days, converted to minutes at the block's rate.
    A block without that dose runs for 0 minutes and is listed in ``no_dose_blocks``.
    """
    blocks = list(
        db.scalars(
            select(Block)
            .where(Block.farm_id == farm.id, Block.status == BlockStatus.complete)
            .order_by(Block.name, Block.id)
        ).all()
    )
    run_times, missing = _run_times(db, farm, blocks, mode)
    demands = _demands(db, farm, blocks, run_times)
    pumps = _pump_hours(db, farm)
    supplies = [(pump_id, flow, scope) for pump_id, flow, scope, _windows in pumps]
    plan = calc.plan_shifts(demands, supplies)
    result = calc.summary(demands, pumps, plan)
    return _check_out(mode, result, plan, missing)


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _snapshot(check: CapacityCheckOut) -> dict[str, Any]:
    encoded = _jsonable(check.model_dump())
    if isinstance(encoded, dict):
        return encoded
    return {}


def _reason(reason: str) -> str:
    cleaned = reason.strip()
    if cleaned == "":
        raise AppError("validation_error", 422, {"reason": "record.reason_required"})
    return cleaned


def record_capacity_decision(
    db: Session,
    farm: Farm,
    user: AppUser,
    body: CapacityDecisionIn,
) -> CapacityDecisionOut:
    """Store the grower's choice. Irrigation plans are unchanged (phase 2)."""
    reason = _reason(body.reason)
    block_ids = None if body.block_ids is None else _unique_ids(body.block_ids)
    if block_ids is not None:
        _require_blocks(db, farm.id, block_ids)
    check = read_capacity_check(db, farm, body.mode)
    row = CapacityDecision(
        farm_id=farm.id,
        choice=body.choice,
        reason=reason,
        block_ids=block_ids,
        mode=body.mode,
        snapshot=_snapshot(check),
        user_id=user.id,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CapacityDecisionOut(
        id=row.id,
        choice=row.choice,
        reason=row.reason,
        block_ids=None if row.block_ids is None else list(row.block_ids),
        mode=row.mode,
        snapshot=check,
        created_at=row.created_at,
    )
