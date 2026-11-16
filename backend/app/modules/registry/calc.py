"""Pure registry calculations. No database and no I/O."""

from collections.abc import Sequence
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Literal


class CalcInputError(ValueError):
    """A required registry input is zero, negative, or otherwise unusable."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(code)


def _positive_code(field: str) -> str:
    return f"registry.{field}_must_be_positive"


def _require_positive_decimal(value: Decimal, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise CalcInputError(field, _positive_code(field))
    return value


def _require_positive_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise CalcInputError(field, _positive_code(field))
    return value


def floor_trees(raw_trees_per_ha: Decimal) -> int:
    """Round a tree density down to a whole number of trees.

    trees_per_ha = floor(raw_trees_per_ha)

    Source: AGRECT system design, Calculation reference — Registry.
    """
    raw = _require_positive_decimal(raw_trees_per_ha, "raw_trees_per_ha")
    return int(raw.to_integral_value(rounding=ROUND_FLOOR))


def trees_per_ha_from_spacing(row_spacing_m: Decimal, tree_spacing_m: Decimal) -> int:
    """Trees per hectare from row spacing and in-row spacing.

    trees_per_ha = floor(10000 / (row_spacing_m × tree_spacing_m))

    Source: AGRECT system design, Calculation reference — Registry.
    """
    row = _require_positive_decimal(row_spacing_m, "row_spacing_m")
    tree = _require_positive_decimal(tree_spacing_m, "tree_spacing_m")
    return floor_trees(Decimal(10000) / (row * tree))


def tree_spacing_from_density(row_spacing_m: Decimal, trees_per_ha: int) -> Decimal:
    """In-row spacing from row spacing and trees per hectare.

    tree_spacing_m = 10000 / (row_spacing_m × trees_per_ha), quantized to 0.01 m
    (ROUND_HALF_UP).

    Source: AGRECT system design, Calculation reference — Registry.
    """
    row = _require_positive_decimal(row_spacing_m, "row_spacing_m")
    count = _require_positive_int(trees_per_ha, "trees_per_ha")
    raw = Decimal(10000) / (row * Decimal(count))
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def trees_per_ha_from_count(trees_count: int, net_area_ha: Decimal) -> int:
    """Trees per hectare from a tree count and the block net area.

    trees_per_ha = floor(trees_count / net_area_ha)

    Source: AGRECT system design, Calculation reference — Registry.
    """
    count = _require_positive_int(trees_count, "trees_count")
    area = _require_positive_decimal(net_area_ha, "net_area_ha")
    return floor_trees(Decimal(count) / area)


def trees_in_block(trees_per_ha: int, net_area_ha: Decimal) -> int:
    """Trees in a block from density and net area.

    trees_in_block = floor(trees_per_ha × net_area_ha)

    Source: AGRECT system design, Calculation reference — Registry.
    """
    count = _require_positive_int(trees_per_ha, "trees_per_ha")
    area = _require_positive_decimal(net_area_ha, "net_area_ha")
    return floor_trees(Decimal(count) * area)


def q_ha_from_layout_m3h(
    row_spacing_m: Decimal,
    laterals_per_row: int,
    emitter_spacing_m: Decimal,
    emitter_flow_lph: Decimal,
) -> Decimal:
    """Drip flow per hectare from the lateral and emitter layout.

    q_ha_m3h = (10000 / row_spacing_m) × laterals_per_row / emitter_spacing_m
        × emitter_flow_lph / 1000

    Source: AGRECT system design, Calculation reference — Registry.
    """
    row = _require_positive_decimal(row_spacing_m, "row_spacing_m")
    laterals = _require_positive_int(laterals_per_row, "laterals_per_row")
    spacing = _require_positive_decimal(emitter_spacing_m, "emitter_spacing_m")
    flow = _require_positive_decimal(emitter_flow_lph, "emitter_flow_lph")
    return (Decimal(10000) / row) * Decimal(laterals) / spacing * flow / Decimal(1000)


def row_length_m_per_ha(row_spacing_m: Decimal) -> Decimal:
    """Metres of tree row per hectare.

    row_m_per_ha = 10000 / row_spacing_m

    Source: AGRECT system design, Calculation reference — Registry.
    """
    row = _require_positive_decimal(row_spacing_m, "row_spacing_m")
    return Decimal(10000) / row


def lateral_length_m_per_ha(row_spacing_m: Decimal, laterals_per_row: int) -> Decimal:
    """Metres of lateral pipe per hectare.

    lateral_m_per_ha = row_length_m_per_ha(row_spacing_m) × laterals_per_row

    Source: AGRECT system design, Calculation reference — Registry.
    """
    laterals = _require_positive_int(laterals_per_row, "laterals_per_row")
    return row_length_m_per_ha(row_spacing_m) * Decimal(laterals)


def emitters_per_ha(
    row_spacing_m: Decimal,
    laterals_per_row: int,
    emitter_spacing_m: Decimal,
) -> Decimal:
    """Emitters per hectare from the lateral layout.

    emitters_per_ha = lateral_length_m_per_ha(row_spacing_m, laterals_per_row)
        / emitter_spacing_m

    Source: AGRECT system design, Calculation reference — Registry.
    """
    spacing = _require_positive_decimal(emitter_spacing_m, "emitter_spacing_m")
    return lateral_length_m_per_ha(row_spacing_m, laterals_per_row) / spacing


def q_ha_from_trees_m3h(
    trees_per_ha: int,
    emitters_per_tree: int,
    flow_per_emitter_lph: Decimal,
) -> Decimal:
    """Flow per hectare for micro-sprinkler or bubbler layouts.

    q_ha_m3h = trees_per_ha × emitters_per_tree × flow_per_emitter_lph / 1000

    Source: AGRECT system design, Calculation reference — Registry.
    """
    trees = _require_positive_int(trees_per_ha, "trees_per_ha")
    emitters = _require_positive_int(emitters_per_tree, "emitters_per_tree")
    flow = _require_positive_decimal(flow_per_emitter_lph, "flow_per_emitter_lph")
    return Decimal(trees) * Decimal(emitters) * flow / Decimal(1000)


def q_block_m3h(plantings: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    """Block flow as the sum of each planting's per-hectare flow times its area.

    q_block_m3h = Σ (q_ha_m3h × area_ha)

    Source: AGRECT system design, Calculation reference — Registry.
    """
    total = Decimal(0)
    for q_ha_m3h, area_ha in plantings:
        flow = _require_positive_decimal(q_ha_m3h, "q_ha_m3h")
        area = _require_positive_decimal(area_ha, "area_ha")
        total += flow * area
    return total


def q_block_from_typed_m3h(
    typed_flow_m3h: Decimal,
    basis: Literal["block", "ha", "valve"],
    net_area_ha: Decimal | None = None,
    valve_flows_m3h: Sequence[Decimal] = (),
) -> Decimal:
    """Block flow from a typed flow and the basis it was entered on.

    block: q_block_m3h = typed_flow_m3h
    ha: q_block_m3h = typed_flow_m3h × net_area_ha
    valve: q_block_m3h = Σ valve_flows_m3h
        (typed_flow_m3h is ignored; valve_flows_m3h must be non-empty)

    Source: AGRECT system design, Calculation reference — Registry.
    """
    if basis == "block":
        return _require_positive_decimal(typed_flow_m3h, "typed_flow_m3h")
    if basis == "ha":
        flow = _require_positive_decimal(typed_flow_m3h, "typed_flow_m3h")
        if net_area_ha is None:
            raise CalcInputError("net_area_ha", _positive_code("net_area_ha"))
        area = _require_positive_decimal(net_area_ha, "net_area_ha")
        return flow * area
    if basis == "valve":
        if not valve_flows_m3h:
            raise CalcInputError("valve_flows_m3h", _positive_code("valve_flows_m3h"))
        total = Decimal(0)
        for flow in valve_flows_m3h:
            total += _require_positive_decimal(flow, "valve_flows_m3h")
        return total
    raise ValueError(basis)


def q_ha_from_block_m3h(q_block_m3h: Decimal, net_area_ha: Decimal) -> Decimal:
    """Flow per hectare from a block flow and the net planted area.

    q_ha_m3h = q_block_m3h / net_area_ha

    Source: AGRECT system design, Calculation reference — Registry.
    """
    flow = _require_positive_decimal(q_block_m3h, "q_block_m3h")
    area = _require_positive_decimal(net_area_ha, "net_area_ha")
    return flow / area


def rate_mm_h(q_block_m3h: Decimal, net_area_ha: Decimal) -> Decimal:
    """Application rate from block flow and net area.

    rate_mm_h = q_block_m3h / (10 × net_area_ha)

    Source: AGRECT system design, Calculation reference — Registry.
    """
    flow = _require_positive_decimal(q_block_m3h, "q_block_m3h")
    area = _require_positive_decimal(net_area_ha, "net_area_ha")
    return flow / (Decimal(10) * area)


def valve_rows(row_from: int, row_to: int, rows_total: int) -> int:
    """Rows covered by one valve.

    rows = row_to − row_from + 1, requiring 1 ≤ row_from ≤ row_to ≤ rows_total.

    Source: AGRECT system design, Calculation reference — Registry.
    """
    if isinstance(row_from, bool) or isinstance(row_to, bool) or isinstance(rows_total, bool):
        raise CalcInputError("valve_rows", "registry.valve_rows_invalid")
    if not (1 <= row_from <= row_to <= rows_total):
        raise CalcInputError("valve_rows", "registry.valve_rows_invalid")
    return row_to - row_from + 1


def valve_area_ha(net_area_ha: Decimal, n_valve_rows: int, rows_total: int) -> Decimal:
    """Net area served by a valve, in proportion to the rows it covers.

    area_ha = net_area_ha × n_valve_rows / rows_total

    Source: AGRECT system design, Calculation reference — Registry.
    """
    area = _require_positive_decimal(net_area_ha, "net_area_ha")
    rows = _require_positive_int(n_valve_rows, "n_valve_rows")
    total = _require_positive_int(rows_total, "rows_total")
    return area * Decimal(rows) / Decimal(total)


def valve_q_m3h(q_block_m3h: Decimal, n_valve_rows: int, rows_total: int) -> Decimal:
    """Valve flow, in proportion to the rows the valve covers.

    q_m3h = q_block_m3h × n_valve_rows / rows_total

    Source: AGRECT system design, Calculation reference — Registry.
    """
    flow = _require_positive_decimal(q_block_m3h, "q_block_m3h")
    rows = _require_positive_int(n_valve_rows, "n_valve_rows")
    total = _require_positive_int(rows_total, "rows_total")
    return flow * Decimal(rows) / Decimal(total)
