"""Pure labour calculations (AGRECT system design — Labour)."""

from decimal import Decimal

import pytest

from app.modules.labour import calc


def test_labour_hours_three_workers_six_hours() -> None:
    assert calc.labour_hours([(3, Decimal("6"))]) == Decimal("18")


def test_labour_hours_sums_entries() -> None:
    assert calc.labour_hours([(3, Decimal("6")), (2, Decimal("6"))]) == Decimal("30")


def test_labour_hours_empty_is_zero() -> None:
    assert calc.labour_hours([]) == Decimal("0")


def test_norm_over_two_operations() -> None:
    hours = calc.labour_hours([(3, Decimal("6"))]) + calc.labour_hours([(2, Decimal("6"))])
    area = Decimal("1.50") + Decimal("1.00")
    assert calc.labour_norm_h_per_ha(hours, area) == Decimal("12.0")


def test_norm_zero_area_is_none() -> None:
    assert calc.labour_norm_h_per_ha(Decimal("18"), Decimal("0")) is None


@pytest.mark.parametrize(
    ("entries", "code"),
    [
        ([(-1, Decimal("6"))], "labour.headcount_invalid"),
        ([(3, Decimal("-1"))], "labour.hours_invalid"),
        ([(3, Decimal("NaN"))], "labour.hours_invalid"),
    ],
)
def test_labour_hours_rejects_bad_input(entries: list[tuple[int, Decimal]], code: str) -> None:
    with pytest.raises(calc.CalcInputError) as exc:
        calc.labour_hours(entries)
    assert exc.value.code == code
