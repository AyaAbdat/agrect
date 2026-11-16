from decimal import ROUND_HALF_UP

import pytest

from app.modules.registry.calc import (
    CalcInputError,
    emitters_per_ha,
    floor_trees,
    lateral_length_m_per_ha,
    q_block_from_typed_m3h,
    q_block_m3h,
    q_ha_from_block_m3h,
    q_ha_from_layout_m3h,
    q_ha_from_trees_m3h,
    rate_mm_h,
    row_length_m_per_ha,
    tree_spacing_from_density,
    trees_in_block,
    trees_per_ha_from_count,
    trees_per_ha_from_spacing,
    valve_area_ha,
    valve_q_m3h,
    valve_rows,
)
from tests.vectors import D, VectorCase, assert_matches, load


@pytest.mark.parametrize("case", load("registry"), ids=lambda case: case["id"])
def test_registry_vector(case: VectorCase) -> None:
    raw = case["input"]
    expected = case["expected"]
    if case["id"] == "registry.density":
        actual = trees_per_ha_from_spacing(D(raw["row_spacing_m"]), D(raw["tree_spacing_m"]))
        assert_matches(actual, expected["trees_per_ha"])
    elif case["id"] == "registry.round_down":
        assert_matches(floor_trees(D(raw["raw_trees_per_ha"])), expected["trees_per_ha"])
    elif case["id"] == "registry.drip_flow":
        q_ha = q_ha_from_layout_m3h(
            D(raw["row_spacing_m"]),
            int(raw["laterals_per_row"]),
            D(raw["emitter_spacing_m"]),
            D(raw["emitter_flow_lph"]),
        )
        assert_matches(q_ha, expected["q_ha_m3h"])
        q_block = q_block_m3h([(q_ha, D(raw["net_area_ha"]))])
        assert_matches(rate_mm_h(q_block, D(raw["net_area_ha"])), expected["rate_mm_h"])
    else:
        raise AssertionError(case["id"])


def test_assert_matches_rounds_half_up() -> None:
    case = {"id": "registry.half_up", "input": {}, "expected": {}}
    assert_matches(D("10.5"), "11")
    assert_matches(D("1.25"), "1.3")
    assert_matches(D("-1.25"), "-1.3")
    with pytest.raises(AssertionError, match="registry.half_up") as raised:
        assert_matches(D("1.24"), "1.3")
    message = str(raised.value)
    assert case["id"] in message
    assert "actual=1.24" in message
    assert "expected=1.3" in message


def test_row_spacing_must_be_positive() -> None:
    for row_spacing in (D("0"), D("-1.5")):
        with pytest.raises(CalcInputError) as raised:
            trees_per_ha_from_spacing(row_spacing, D("1.50"))
        assert raised.value.field == "row_spacing_m"
        assert raised.value.code == "registry.row_spacing_m_must_be_positive"


def test_spacing_from_density_round_trip() -> None:
    assert tree_spacing_from_density(D("3.00"), 2222) == D("1.50")


def test_trees_per_ha_from_count() -> None:
    assert trees_per_ha_from_count(1000, D("0.45")) == 2222


def test_trees_in_block_floors() -> None:
    assert trees_in_block(2222, D("0.45")) == 999


def test_two_plantings_summed() -> None:
    total = q_block_m3h([(D("10"), D("1.5")), (D("4"), D("2"))])
    assert total == D("23")


def test_typed_basis_block_ha_valve() -> None:
    assert q_block_from_typed_m3h(D("12.5"), "block", D("3")) == D("12.5")
    assert q_block_from_typed_m3h(D("10"), "ha", D("2.5")) == D("25")
    assert q_block_from_typed_m3h(D("999"), "valve", D("3"), [D("1.5"), D("2.5")]) == D("4")
    with pytest.raises(CalcInputError) as raised:
        q_block_from_typed_m3h(D("1"), "valve", D("1"))
    assert raised.value.code == "registry.valve_flows_m3h_must_be_positive"


def test_q_ha_from_trees() -> None:
    assert q_ha_from_trees_m3h(1000, 2, D("4")) == D("8")


def test_q_ha_from_block_flow() -> None:
    actual = q_ha_from_block_m3h(D("40"), D("1.50"))
    assert actual.quantize(D("0.01"), rounding=ROUND_HALF_UP) == D("26.67")


def test_layout_flow_keeps_full_precision() -> None:
    q_ha = q_ha_from_layout_m3h(D("4.00"), 2, D("0.75"), D("4.0"))
    assert q_ha != q_ha.quantize(D("0.01"))


def test_valve_rows_one_third() -> None:
    assert valve_rows(1, 40, 120) == 40
    net = D("3")
    flow = D("9")
    assert valve_area_ha(net, 40, 120) == net / D("3")
    assert valve_q_m3h(flow, 40, 120) == flow / D("3")


@pytest.mark.parametrize(("row_from", "row_to"), [(0, 10), (50, 40), (1, 130)])
def test_valve_rows_invalid(row_from: int, row_to: int) -> None:
    with pytest.raises(CalcInputError) as raised:
        valve_rows(row_from, row_to, 120)
    assert raised.value.code == "registry.valve_rows_invalid"


def test_emitters_per_ha_matches_layout_flow() -> None:
    raw = next(case["input"] for case in load("registry") if case["id"] == "registry.drip_flow")
    row = D(raw["row_spacing_m"])
    laterals = int(raw["laterals_per_row"])
    spacing = D(raw["emitter_spacing_m"])
    flow = D(raw["emitter_flow_lph"])
    assert row_length_m_per_ha(row) == D("2500")
    assert lateral_length_m_per_ha(row, laterals) == D("5000")
    emitters = emitters_per_ha(row, laterals, spacing)
    assert emitters * flow / D("1000") == q_ha_from_layout_m3h(row, laterals, spacing, flow)


def test_valve_areas_of_full_split_sum_to_net() -> None:
    net = D("6.3")
    flow = D("12.6")
    rows_total = 120
    ranges = [(1, 30), (31, 70), (71, 120)]
    area_sum = D("0")
    flow_sum = D("0")
    covered = 0
    for row_from, row_to in ranges:
        rows = valve_rows(row_from, row_to, rows_total)
        covered += rows
        area_sum += valve_area_ha(net, rows, rows_total)
        flow_sum += valve_q_m3h(flow, rows, rows_total)
    assert covered == rows_total
    assert area_sum == net
    assert flow_sum == flow
