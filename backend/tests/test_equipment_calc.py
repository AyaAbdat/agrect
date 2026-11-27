"""Pure equipment calculations (AGRECT system design — Equipment)."""

from datetime import date
from decimal import Decimal

import pytest

from app.modules.equipment import calc


def test_work_rate() -> None:
    assert calc.work_rate_ha_h(Decimal("1.50"), Decimal("2")) == Decimal("0.75")


def test_work_rate_zero_hours_is_none() -> None:
    assert calc.work_rate_ha_h(Decimal("1.50"), Decimal("0")) is None


def test_current_engine_hours() -> None:
    assert calc.current_engine_hours(Decimal("1000"), [Decimal("2")]) == Decimal("1002")
    assert calc.current_engine_hours(Decimal("1000"), []) == Decimal("1000")


def test_current_engine_hours_rejects_negative() -> None:
    with pytest.raises(calc.CalcInputError):
        calc.current_engine_hours(Decimal("1000"), [Decimal("-1")])


def _hours_due(current_h: str) -> calc.MaintenanceDue:
    return calc.maintenance_due(
        Decimal("800"), Decimal("250"), Decimal(current_h), None, None, date(2026, 11, 27)
    )


def test_maintenance_by_hours() -> None:
    not_yet = _hours_due("1002")
    assert not_yet.next_due_h == Decimal("1050")
    assert not_yet.due_by_hours is False
    assert not_yet.overdue is False
    assert not_yet.next_due_date is None
    assert not_yet.due_by_date is False

    exactly = _hours_due("1050")
    assert exactly.due_by_hours is True
    assert exactly.overdue is False

    past = _hours_due("1060")
    assert past.due_by_hours is True
    assert past.overdue is True


def test_maintenance_by_days() -> None:
    last = date(2026, 1, 1)
    before = calc.maintenance_due(None, None, None, last, 180, date(2026, 6, 29))
    assert before.next_due_date == date(2026, 6, 30)
    assert before.due_by_date is False
    on_day = calc.maintenance_due(None, None, None, last, 180, date(2026, 6, 30))
    assert on_day.due_by_date is True
    assert on_day.overdue is False
    after = calc.maintenance_due(None, None, None, last, 180, date(2026, 7, 1))
    assert after.overdue is True


def test_maintenance_both_intervals_whichever_first() -> None:
    # Hours not reached, but the date has passed: due by date.
    due = calc.maintenance_due(
        Decimal("800"),
        Decimal("250"),
        Decimal("900"),
        date(2026, 1, 1),
        180,
        date(2026, 8, 1),
    )
    assert due.due_by_hours is False
    assert due.due_by_date is True
    assert due.overdue is True
    assert due.next_due_h == Decimal("1050")
    assert due.next_due_date == date(2026, 6, 30)


def test_maintenance_no_interval_known() -> None:
    due = calc.maintenance_due(None, Decimal("250"), Decimal("1000"), None, 180, date(2026, 8, 1))
    assert due.next_due_h is None
    assert due.next_due_date is None
    assert due.due_by_hours is False
    assert due.due_by_date is False
    assert due.overdue is False
