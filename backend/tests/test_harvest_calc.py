"""Harvest calc vectors and error cases."""

import pytest

from app.modules.harvest.calc import (
    CalcInputError,
    basis_area_ha,
    harvest_kg,
    kg_per_ha,
)
from tests.vectors import D, VectorCase, assert_matches, load


@pytest.mark.parametrize(
    "case",
    [c for c in load("records") if c["id"] == "records.harvest_crates"],
    ids=lambda case: case["id"],
)
def test_records_harvest_vector(case: VectorCase) -> None:
    raw = case["input"]
    expected = case["expected"]
    kg = harvest_kg(D(raw["quantity"]), "crate", D(raw["unit_weight_kg"]))
    area = D(raw["area_ha"])
    assert_matches(kg, expected["kg"])
    assert_matches(kg_per_ha(kg, area), expected["kg_ha"])


def test_same_yield_as_tonnes_valves_rows_trees() -> None:
    """Same harvest as crates expressed as t, valves, rows and trees -> 3000 kg/ha."""
    case = next(c for c in load("records") if c["id"] == "records.harvest_crates")
    expected_kg = case["expected"]["kg"]
    expected_kg_ha = case["expected"]["kg_ha"]
    net = D("1.50")

    as_tonnes = harvest_kg(D("4.5"), "t")
    assert_matches(as_tonnes, expected_kg)
    assert_matches(kg_per_ha(as_tonnes, net), expected_kg_ha)

    valve_a = basis_area_ha("valve", net_area_ha=net, valve_area_ha=D("0.72"))
    valve_b = basis_area_ha("valve", net_area_ha=net, valve_area_ha=D("0.78"))
    kg_a = harvest_kg(D("2160"), "kg")
    kg_b = harvest_kg(D("2340"), "kg")
    assert_matches(kg_a + kg_b, expected_kg)
    assert_matches(kg_per_ha(kg_a, valve_a), expected_kg_ha)
    assert_matches(kg_per_ha(kg_b, valve_b), expected_kg_ha)

    rows_area = basis_area_ha(
        "rows",
        net_area_ha=net,
        rows_picked=D("25"),
        rows_total=25,
    )
    assert_matches(kg_per_ha(harvest_kg(D("4500"), "kg"), rows_area), expected_kg_ha)

    trees_per_ha = 1250
    trees_picked = D(str(trees_per_ha)) * net
    trees_area = basis_area_ha(
        "trees",
        net_area_ha=net,
        trees_picked=trees_picked,
        trees_per_ha=trees_per_ha,
    )
    assert_matches(kg_per_ha(harvest_kg(D("4500"), "kg"), trees_area), expected_kg_ha)


def test_crate_requires_unit_weight() -> None:
    with pytest.raises(CalcInputError) as raised:
        harvest_kg(D("10"), "crate", None)
    assert raised.value.code == "harvest.unit_weight_required"
    assert raised.value.field == "unit_weight_kg"

    with pytest.raises(CalcInputError) as raised_zero:
        harvest_kg(D("10"), "bin", D("0"))
    assert raised_zero.value.code == "harvest.unit_weight_required"


def test_rows_exceed_total() -> None:
    with pytest.raises(CalcInputError) as raised:
        basis_area_ha(
            "rows",
            net_area_ha=D("1.50"),
            rows_picked=D("26"),
            rows_total=25,
        )
    assert raised.value.code == "harvest.rows_exceed_total"


def test_trees_missing_inputs() -> None:
    with pytest.raises(CalcInputError) as no_trees:
        basis_area_ha("trees", net_area_ha=D("1.50"), trees_per_ha=1250)
    assert no_trees.value.code == "harvest.trees_required"

    with pytest.raises(CalcInputError) as no_density:
        basis_area_ha("trees", net_area_ha=D("1.50"), trees_picked=D("100"))
    assert no_density.value.code == "harvest.trees_per_ha_missing"
