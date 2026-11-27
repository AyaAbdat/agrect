"""Pure inputs-and-cost calculations."""

from decimal import Decimal

import pytest

from app.modules.inputs import calc


def test_convert_ml_to_l() -> None:
    assert calc.convert_qty(Decimal("2250"), "ml", "l") == Decimal("2.25")


def test_line_cost_2250ml_at_1200_per_l() -> None:
    qty = calc.convert_qty(Decimal("2250"), "ml", "l")
    assert calc.line_cost(qty, Decimal("1200")) == Decimal("2700")


def test_convert_and_cost_500g_at_800_per_kg() -> None:
    qty = calc.convert_qty(Decimal("500"), "g", "kg")
    assert qty == Decimal("0.5")
    assert calc.line_cost(qty, Decimal("800")) == Decimal("400")


def test_convert_same_unit_is_identity() -> None:
    assert calc.convert_qty(Decimal("3"), "unit", "unit") == Decimal("3")
    assert calc.convert_qty(Decimal("4.2"), "l", "l") == Decimal("4.2")


def test_convert_incompatible_units_raises() -> None:
    with pytest.raises(calc.CalcInputError) as exc:
        calc.convert_qty(Decimal("1"), "kg", "l")
    assert exc.value.code == "inputs.unit_mismatch"


def test_convert_unit_to_kg_raises() -> None:
    with pytest.raises(calc.CalcInputError) as exc:
        calc.convert_qty(Decimal("1"), "unit", "kg")
    assert exc.value.code == "inputs.unit_mismatch"


def test_cost_per_ha() -> None:
    assert calc.cost_per_ha(Decimal("2700"), Decimal("1.50")) == Decimal("1800")


def test_cost_per_ha_zero_area_raises() -> None:
    with pytest.raises(calc.CalcInputError) as exc:
        calc.cost_per_ha(Decimal("100"), Decimal("0"))
    assert exc.value.code == "inputs.area_must_be_positive"


def test_water_cost_60m3_at_5() -> None:
    assert calc.water_cost(Decimal("60"), Decimal("5")) == Decimal("300")
