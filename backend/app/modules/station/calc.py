"""Pure fertigation-station calculations. No database and no I/O."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import time
from decimal import Decimal

_DAY_SECONDS = Decimal(86400)
_HOUR_SECONDS = Decimal(3600)
_DAY_HOURS = Decimal(24)
_MINUTES_PER_HOUR = Decimal(60)


class AllBlocks:
    """Marker: the pump can irrigate every block on the farm."""


ALL = AllBlocks()

PumpScope = frozenset[uuid.UUID] | AllBlocks
ValveDemand = tuple[uuid.UUID, uuid.UUID, Decimal, Decimal]
PumpSupply = tuple[uuid.UUID, Decimal, PumpScope]
PumpHours = tuple[uuid.UUID, Decimal, PumpScope, Sequence[tuple[time, time]]]


@dataclass(frozen=True)
class ShiftValve:
    valve_id: uuid.UUID
    block_id: uuid.UUID
    q_m3h: Decimal
    run_time_min: Decimal


@dataclass(frozen=True)
class Shift:
    valves: tuple[ShiftValve, ...]
    flow_m3h: Decimal
    time_min: Decimal


@dataclass(frozen=True)
class ShiftPlan:
    shifts: tuple[Shift, ...]
    cannot_supply: tuple[ShiftValve, ...]


@dataclass(frozen=True)
class CapacitySummary:
    open_together_flow_m3h: Decimal
    pumps_flow_m3h: Decimal
    short_by_m3h: Decimal
    hours_needed: Decimal
    hours_available: Decimal | None
    fits_in_hours: bool | None


def _seconds(value: time) -> Decimal:
    return (
        Decimal(value.hour) * _HOUR_SECONDS
        + Decimal(value.minute) * _MINUTES_PER_HOUR
        + Decimal(value.second)
        + Decimal(value.microsecond) / Decimal(1000000)
    )


def window_hours(start: time, end: time) -> Decimal:
    """Hours covered by one farm-local window.

    When end is later than start, hours = (end − start) / 1 h.
    When end is earlier, the window crosses midnight:
    hours = (24:00 − start) + end.
    Equal clock times cover the whole day: 24 h.

    Source: AGRECT system design — Registry and fertigation station, capacity check.
    """
    if start == end:
        return _DAY_HOURS
    start_s = _seconds(start)
    end_s = _seconds(end)
    if end_s > start_s:
        span = end_s - start_s
    else:
        span = _DAY_SECONDS - start_s + end_s
    return span / _HOUR_SECONDS


def pump_hours_available(windows: Sequence[tuple[time, time]]) -> Decimal:
    """Hours a pump may run in one farm-local day.

    hours = min(24, Σ window_hours). No windows means the pump may run all day: 24 h.

    Source: AGRECT system design — Registry and fertigation station, capacity check.
    """
    if not windows:
        return _DAY_HOURS
    total = sum((window_hours(start, end) for start, end in windows), Decimal(0))
    if total > _DAY_HOURS:
        return _DAY_HOURS
    return total


def _covers(scope: PumpScope, block_ids: set[uuid.UUID]) -> bool:
    if isinstance(scope, AllBlocks):
        return True
    return block_ids <= scope


def _capable_flow(pumps: Sequence[PumpSupply], block_ids: set[uuid.UUID]) -> Decimal:
    total = Decimal(0)
    for _pump_id, flow_m3h, scope in pumps:
        if _covers(scope, block_ids):
            total += flow_m3h
    return total


def _valve(row: ValveDemand) -> ShiftValve:
    valve_id, block_id, flow_m3h, run_time_min = row
    return ShiftValve(
        valve_id=valve_id,
        block_id=block_id,
        q_m3h=flow_m3h,
        run_time_min=run_time_min,
    )


class _OpenShift:
    def __init__(self, valve: ShiftValve) -> None:
        self.valves: list[ShiftValve] = [valve]
        self.flow_m3h = valve.q_m3h
        self.time_min = valve.run_time_min
        self.block_ids = {valve.block_id}

    def add(self, valve: ShiftValve) -> None:
        self.valves.append(valve)
        self.flow_m3h += valve.q_m3h
        if valve.run_time_min > self.time_min:
            self.time_min = valve.run_time_min
        self.block_ids.add(valve.block_id)

    def freeze(self) -> Shift:
        return Shift(
            valves=tuple(self.valves),
            flow_m3h=self.flow_m3h,
            time_min=self.time_min,
        )


def plan_shifts(valves: Sequence[ValveDemand], pumps: Sequence[PumpSupply]) -> ShiftPlan:
    """Group valves that may open together into shifts.

    Valves are taken largest flow first (first-fit decreasing). A valve joins an
    existing shift only when

        Σ q of the shift + q <= Σ flow of the pumps that can serve every block
        in that shift (including the valve's block).

    Otherwise it opens a new shift. A valve whose own q is greater than the flow
    of every pump that can serve its block is listed in ``cannot_supply`` and is
    not placed. Each shift's time is the longest ``run_time_min`` among its valves.

    Source: AGRECT system design — Registry and fertigation station, capacity check.
    """
    ordered = sorted(valves, key=lambda row: row[2], reverse=True)
    shifts: list[_OpenShift] = []
    cannot_supply: list[ShiftValve] = []
    for row in ordered:
        valve = _valve(row)
        if valve.q_m3h > _capable_flow(pumps, {valve.block_id}):
            cannot_supply.append(valve)
            continue
        placed = False
        for shift in shifts:
            blocks = set(shift.block_ids)
            blocks.add(valve.block_id)
            if shift.flow_m3h + valve.q_m3h <= _capable_flow(pumps, blocks):
                shift.add(valve)
                placed = True
                break
        if not placed:
            shifts.append(_OpenShift(valve))
    return ShiftPlan(
        shifts=tuple(shift.freeze() for shift in shifts),
        cannot_supply=tuple(cannot_supply),
    )


def hours_needed(shifts: Sequence[Shift]) -> Decimal:
    """Pumping hours required to run every shift, one after another.

    hours_needed = Σ shift time_min / 60

    Source: AGRECT system design — Registry and fertigation station, capacity check.
    """
    total_min = sum((shift.time_min for shift in shifts), Decimal(0))
    return total_min / _MINUTES_PER_HOUR


def _used_windows(
    valves: Sequence[ValveDemand],
    pumps: Sequence[PumpHours],
) -> list[Sequence[tuple[time, time]]]:
    """Windows of pumps that can serve at least one listed block.

    With no valves, every pump counts: the limit is the station's own.
    """
    block_ids = {row[1] for row in valves}
    chosen: list[Sequence[tuple[time, time]]] = []
    for _pump_id, _flow, scope, windows in pumps:
        if not block_ids or any(_covers(scope, {block_id}) for block_id in block_ids):
            chosen.append(windows)
    return chosen


def _hours_available(pumps: Sequence[PumpHours], valves: Sequence[ValveDemand]) -> Decimal | None:
    """Minimum daily hours of the pumps in play.

    Null when none of those pumps has a window. A pump with no window counts as
    24 h only when some other pump in play has a window.
    """
    windows = _used_windows(valves, pumps)
    if not windows or not any(item for item in windows):
        return None
    return min(pump_hours_available(item) for item in windows)


def summary(
    valves: Sequence[ValveDemand],
    pumps: Sequence[PumpHours],
    plan: ShiftPlan,
) -> CapacitySummary:
    """Compare open-valve demand with the pumps, in flow and in hours.

    open_together_flow_m3h = Σ q of every listed valve (placed or not).
    pumps_flow_m3h = Σ pump flow.
    short_by_m3h = max(0, open_together_flow_m3h − pumps_flow_m3h).
    hours_needed = Σ shift time / 60.
    hours_available = min pump_hours_available of the pumps that can serve a
    listed block, or null when no such pump has a window.
    fits_in_hours = hours_needed <= hours_available, or null when hours are unset.

    Source: AGRECT system design — Registry and fertigation station, capacity check.
    """
    open_together = sum((row[2] for row in valves), Decimal(0))
    pumps_flow = sum((pump[1] for pump in pumps), Decimal(0))
    short_by = open_together - pumps_flow
    if short_by < 0:
        short_by = Decimal(0)
    needed = hours_needed(plan.shifts)
    available = _hours_available(pumps, valves)
    fits = None if available is None else needed <= available
    return CapacitySummary(
        open_together_flow_m3h=open_together,
        pumps_flow_m3h=pumps_flow,
        short_by_m3h=short_by,
        hours_needed=needed,
        hours_available=available,
        fits_in_hours=fits,
    )
