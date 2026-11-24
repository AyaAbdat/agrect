import uuid
from datetime import time
from decimal import Decimal

from app.modules.station.calc import (
    ALL,
    hours_needed,
    plan_shifts,
    pump_hours_available,
    summary,
    window_hours,
)


def test_valves_that_fill_the_pump_share_one_shift() -> None:
    block_id = uuid.uuid4()
    pump_id = uuid.uuid4()
    plan = plan_shifts(
        [
            (uuid.uuid4(), block_id, Decimal("19.2"), Decimal("30")),
            (uuid.uuid4(), block_id, Decimal("20.8"), Decimal("45")),
        ],
        [(pump_id, Decimal("40"), ALL)],
    )
    assert plan.cannot_supply == ()
    assert len(plan.shifts) == 1
    assert plan.shifts[0].flow_m3h == Decimal("40.0")
    assert plan.shifts[0].time_min == Decimal("45")


def test_a_valve_that_does_not_fit_opens_a_second_shift() -> None:
    block_id = uuid.uuid4()
    pump_id = uuid.uuid4()
    plan = plan_shifts(
        [
            (uuid.uuid4(), block_id, Decimal("19.2"), Decimal("90")),
            (uuid.uuid4(), block_id, Decimal("20.8"), Decimal("60")),
            (uuid.uuid4(), block_id, Decimal("25"), Decimal("30")),
        ],
        [(pump_id, Decimal("40"), ALL)],
    )
    assert plan.cannot_supply == ()
    assert len(plan.shifts) == 2
    assert plan.shifts[0].flow_m3h == Decimal("25")
    assert plan.shifts[0].time_min == Decimal("30")
    assert plan.shifts[1].flow_m3h == Decimal("40.0")
    assert plan.shifts[1].time_min == Decimal("90")
    assert hours_needed(plan.shifts) == Decimal("2")


def test_a_valve_larger_than_the_pumps_cannot_be_supplied() -> None:
    block_id = uuid.uuid4()
    plan = plan_shifts(
        [(uuid.uuid4(), block_id, Decimal("50"), Decimal("10"))],
        [(uuid.uuid4(), Decimal("40"), ALL)],
    )
    assert plan.shifts == ()
    assert len(plan.cannot_supply) == 1
    assert plan.cannot_supply[0].q_m3h == Decimal("50")


def test_pump_flows_add_when_each_can_serve_the_block() -> None:
    block_id = uuid.uuid4()
    pumps = [
        (uuid.uuid4(), Decimal("15"), ALL),
        (uuid.uuid4(), Decimal("25"), ALL),
    ]
    fitted = plan_shifts(
        [(uuid.uuid4(), block_id, Decimal("40"), Decimal("10"))],
        pumps,
    )
    assert len(fitted.shifts) == 1
    assert fitted.shifts[0].flow_m3h == Decimal("40")
    refused = plan_shifts(
        [(uuid.uuid4(), block_id, Decimal("40.1"), Decimal("10"))],
        pumps,
    )
    assert refused.shifts == ()
    assert len(refused.cannot_supply) == 1


def test_a_pump_limited_to_block_a_cannot_serve_block_b() -> None:
    block_a = uuid.uuid4()
    block_b = uuid.uuid4()
    valve_a = uuid.uuid4()
    valve_b = uuid.uuid4()
    plan = plan_shifts(
        [
            (valve_b, block_b, Decimal("10"), Decimal("30")),
            (valve_a, block_a, Decimal("10"), Decimal("20")),
        ],
        [(uuid.uuid4(), Decimal("40"), frozenset({block_a}))],
    )
    assert len(plan.shifts) == 1
    assert plan.shifts[0].valves[0].valve_id == valve_a
    assert len(plan.cannot_supply) == 1
    assert plan.cannot_supply[0].valve_id == valve_b


def test_window_hours_cross_midnight_and_empty_windows_are_a_full_day() -> None:
    assert window_hours(time(22, 0), time(6, 0)) == Decimal("8")
    assert window_hours(time(6, 0), time(22, 0)) == Decimal("16")
    assert window_hours(time(8, 0), time(8, 0)) == Decimal("24")
    assert pump_hours_available(()) == Decimal("24")
    eight = (time(22, 0), time(6, 0))
    twelve = (time(8, 0), time(20, 0))
    assert pump_hours_available((eight, twelve)) == Decimal("20")
    ten = (time(8, 0), time(18, 0))
    assert pump_hours_available((ten, ten, ten)) == Decimal("24")


def test_summary_reports_the_shortfall_and_unset_hours() -> None:
    block_id = uuid.uuid4()
    pump_id = uuid.uuid4()
    valves = [
        (uuid.uuid4(), block_id, Decimal("20"), Decimal("300")),
        (uuid.uuid4(), block_id, Decimal("20"), Decimal("300")),
    ]
    pumps = [(pump_id, Decimal("30"), ALL)]
    plan = plan_shifts(valves, pumps)
    assert len(plan.shifts) == 2
    quiet = summary(valves, [(pump_id, Decimal("30"), ALL, ())], plan)
    assert quiet.open_together_flow_m3h == Decimal("40")
    assert quiet.pumps_flow_m3h == Decimal("30")
    assert quiet.short_by_m3h == Decimal("10")
    assert quiet.hours_needed == Decimal("10")
    assert quiet.hours_available is None
    assert quiet.fits_in_hours is None
    limited = summary(
        valves,
        [(pump_id, Decimal("30"), ALL, ((time(22, 0), time(6, 0)),))],
        plan,
    )
    assert limited.hours_available == Decimal("8")
    assert limited.fits_in_hours is False
    assert hours_needed(plan.shifts) == quiet.hours_needed
