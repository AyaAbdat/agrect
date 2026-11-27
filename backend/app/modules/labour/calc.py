"""Pure labour calculations. No database and no I/O.

Source: AGRECT system design — Labour.
"""

from collections.abc import Iterable
from decimal import Decimal


class CalcInputError(ValueError):
    """A labour input is missing, negative, or non-finite."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(code)


def _require_non_negative(value: Decimal, field: str, code: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise CalcInputError(field, code)
    return value


def labour_hours(entries: Iterable[tuple[int, Decimal]]) -> Decimal:
    """Total labour hours = Σ workers_count × hours_each.

    Each entry is ``(workers_count, hours_each)``; both must be non-negative.

    Source: AGRECT system design — Labour.
    """
    total = Decimal(0)
    for workers_count, hours_each in entries:
        if isinstance(workers_count, bool) or not isinstance(workers_count, int):
            raise CalcInputError("workers_count", "labour.headcount_invalid")
        if workers_count < 0:
            raise CalcInputError("workers_count", "labour.headcount_invalid")
        hours = _require_non_negative(hours_each, "hours_each", "labour.hours_invalid")
        total += Decimal(workers_count) * hours
    return total


def labour_norm_h_per_ha(total_hours: Decimal, total_area_ha: Decimal) -> Decimal | None:
    """Labour norm (h/ha) = Σ hours / Σ area worked, per operation type and crop.

    Returns ``None`` when the total area is zero (no norm can be given).

    Source: AGRECT system design — Labour.
    """
    hours = _require_non_negative(total_hours, "total_hours", "labour.hours_invalid")
    area = _require_non_negative(total_area_ha, "total_area_ha", "labour.area_invalid")
    if area == 0:
        return None
    return hours / area
