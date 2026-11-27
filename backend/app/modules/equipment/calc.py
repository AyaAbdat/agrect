"""Pure equipment calculations. No database and no I/O.

Source: AGRECT system design — Equipment.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal


class CalcInputError(ValueError):
    """An equipment input is missing, negative, or non-finite."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(code)


def _require_non_negative(value: Decimal, field: str, code: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise CalcInputError(field, code)
    return value


def work_rate_ha_h(area_ha: Decimal, hours: Decimal) -> Decimal | None:
    """Work rate (ha/h) = area worked / machine hours; ``None`` when hours is 0.

    Source: AGRECT system design — Equipment.
    """
    area = _require_non_negative(area_ha, "area_ha", "equipment.area_invalid")
    spent = _require_non_negative(hours, "hours", "equipment.hours_invalid")
    if spent == 0:
        return None
    return area / spent


def current_engine_hours(reading_h: Decimal, use_hours_since_reading: Iterable[Decimal]) -> Decimal:
    """Current engine hours = last reading + Σ machine hours logged after the reading.

    Source: AGRECT system design — Equipment.
    """
    total = _require_non_negative(reading_h, "reading_h", "equipment.hours_invalid")
    for hours in use_hours_since_reading:
        total += _require_non_negative(hours, "hours", "equipment.hours_invalid")
    return total


@dataclass(frozen=True)
class MaintenanceDue:
    due_by_hours: bool
    due_by_date: bool
    next_due_h: Decimal | None
    next_due_date: date | None
    overdue: bool


def maintenance_due(
    last_done_h: Decimal | None,
    interval_h: Decimal | None,
    current_h: Decimal | None,
    last_done_date: date | None,
    interval_days: int | None,
    today: date,
) -> MaintenanceDue:
    """Maintenance due by hours or by days, whichever comes first.

    next_due_h = last_done_h + interval_h; due by hours when current_h >= next_due_h.
    next_due_date = last_done_date + interval_days; due by date when today >= next_due_date.
    Overdue when past either point (current_h > next_due_h or today > next_due_date).
    A side whose inputs are missing gives no next point and is never due.

    Source: AGRECT system design — Equipment.
    """
    next_h: Decimal | None = None
    if last_done_h is not None and interval_h is not None:
        next_h = _require_non_negative(
            last_done_h, "last_done_h", "equipment.hours_invalid"
        ) + _require_non_negative(interval_h, "interval_h", "equipment.interval_invalid")
    next_date: date | None = None
    if last_done_date is not None and interval_days is not None:
        if interval_days < 0:
            raise CalcInputError("interval_days", "equipment.interval_invalid")
        next_date = last_done_date + timedelta(days=interval_days)
    due_h = next_h is not None and current_h is not None and current_h >= next_h
    due_d = next_date is not None and today >= next_date
    over_h = next_h is not None and current_h is not None and current_h > next_h
    over_d = next_date is not None and today > next_date
    return MaintenanceDue(
        due_by_hours=due_h,
        due_by_date=due_d,
        next_due_h=next_h,
        next_due_date=next_date,
        overdue=over_h or over_d,
    )
