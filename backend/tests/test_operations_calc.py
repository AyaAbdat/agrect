"""Operations calc: product totals, area worked, PHI boundary."""

from datetime import date

import pytest

from app.modules.operations.calc import (
    CalcInputError,
    area_worked_ha,
    nutrient_applied_kg_ha,
    preharvest_ok,
    product_total,
)
from tests.vectors import D, VectorCase, assert_matches, load


@pytest.mark.parametrize(
    "case",
    [c for c in load("records") if c["id"] == "records.product_concentration"],
    ids=lambda case: case["id"],
)
def test_records_product_concentration_vector(case: VectorCase) -> None:
    """150 mL / 100 L × 1000 L/ha × 2.00 ha -> 3000 mL = 3.0 L; unit kept as mL."""
    raw = case["input"]
    total_ml = product_total(
        D(raw["rate_ml_per_100l"]),
        "per_100l",
        D(raw["area_ha"]),
        D(raw["water_l_ha"]),
    )
    assert_matches(total_ml / D("1000"), case["expected"]["total_l"])
    assert total_ml == D("3000")


def test_product_total_per_ha() -> None:
    assert product_total(D("2.5"), "per_ha", D("1.50")) == D("3.75")


def test_product_total_per_block() -> None:
    assert product_total(D("12"), "per_block", D("1.50")) == D("12")


def test_product_total_per_100l_requires_water() -> None:
    with pytest.raises(CalcInputError) as raised:
        product_total(D("150"), "per_100l", D("2.00"), None)
    assert raised.value.code == "operations.water_required"
    assert raised.value.field == "water_l_ha"


def test_area_worked_whole_block() -> None:
    assert area_worked_ha(D("1.50"), None) == D("1.50")
    assert area_worked_ha(D("1.50"), []) == D("1.50")


def test_area_worked_valve_subset() -> None:
    assert area_worked_ha(D("1.50"), [D("0.72"), D("0.78")]) == D("1.50")
    assert area_worked_ha(D("1.50"), [D("0.72")]) == D("0.72")


def test_nutrient_applied() -> None:
    assert nutrient_applied_kg_ha(D("100"), D("0.15")) == D("15")


def test_preharvest_boundary_equal_ok() -> None:
    ok, days_since, days_needed = preharvest_ok(
        date(2026, 9, 21),
        date(2026, 8, 31),
        21,
    )
    assert ok is True
    assert days_since == 21
    assert days_needed == 21


def test_preharvest_warns_when_short() -> None:
    ok, days_since, days_needed = preharvest_ok(
        date(2026, 9, 10),
        date(2026, 8, 31),
        21,
    )
    assert ok is False
    assert days_since == 10
    assert days_needed == 21
