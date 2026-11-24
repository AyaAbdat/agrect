"""Pure harvest calculations. No database and no I/O."""

from decimal import Decimal
from typing import Literal

HarvestUnit = Literal["kg", "t", "crate", "bin"]
HarvestBasis = Literal["block", "valve", "rows", "trees"]


class CalcInputError(ValueError):
    """A harvest input is missing, zero, or outside its allowed range."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(code)


def _require_finite(value: Decimal, field: str, code: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CalcInputError(field, code)
    return value


def _require_positive(value: Decimal, field: str, code: str) -> Decimal:
    parsed = _require_finite(value, field, code)
    if parsed <= 0:
        raise CalcInputError(field, code)
    return parsed


def harvest_kg(
    quantity: Decimal,
    unit: HarvestUnit,
    unit_weight_kg: Decimal | None = None,
) -> Decimal:
    """Convert a harvest quantity to kilograms.

    kg -> quantity
    t -> quantity × 1000
    crate | bin -> quantity × unit_weight_kg (required, > 0)

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    amount = _require_positive(quantity, "quantity", "harvest.quantity_must_be_positive")
    if unit == "kg":
        return amount
    if unit == "t":
        return amount * Decimal(1000)
    if unit in ("crate", "bin"):
        if unit_weight_kg is None:
            raise CalcInputError("unit_weight_kg", "harvest.unit_weight_required")
        weight = _require_positive(
            unit_weight_kg,
            "unit_weight_kg",
            "harvest.unit_weight_required",
        )
        return amount * weight
    raise CalcInputError("unit", "harvest.unit_invalid")


def basis_area_ha(
    basis: HarvestBasis,
    *,
    net_area_ha: Decimal,
    valve_area_ha: Decimal | None = None,
    rows_picked: Decimal | None = None,
    rows_total: Decimal | int | None = None,
    trees_picked: Decimal | None = None,
    trees_per_ha: Decimal | int | None = None,
) -> Decimal:
    """Net planted area (ha) covered by one harvest entry.

    block -> net_area_ha
    valve -> valve_area_ha
    rows -> net_area_ha × rows_picked / rows_total
    trees -> trees_picked / trees_per_ha

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    if basis == "block":
        return _require_positive(net_area_ha, "net_area_ha", "harvest.net_area_required")
    if basis == "valve":
        if valve_area_ha is None:
            raise CalcInputError("valve_id", "harvest.valve_required")
        return _require_positive(valve_area_ha, "valve_id", "harvest.valve_required")
    if basis == "rows":
        if rows_picked is None:
            raise CalcInputError("basis_count", "harvest.rows_required")
        if rows_total is None:
            raise CalcInputError("rows_total", "harvest.rows_total_missing")
        picked = _require_positive(rows_picked, "basis_count", "harvest.rows_required")
        total = _require_positive(Decimal(rows_total), "rows_total", "harvest.rows_total_missing")
        if picked > total:
            raise CalcInputError("basis_count", "harvest.rows_exceed_total")
        area = _require_positive(net_area_ha, "net_area_ha", "harvest.net_area_required")
        return area * picked / total
    if basis == "trees":
        if trees_picked is None:
            raise CalcInputError("basis_count", "harvest.trees_required")
        if trees_per_ha is None:
            raise CalcInputError("trees_per_ha", "harvest.trees_per_ha_missing")
        picked = _require_positive(trees_picked, "basis_count", "harvest.trees_required")
        density = _require_positive(
            Decimal(trees_per_ha),
            "trees_per_ha",
            "harvest.trees_per_ha_missing",
        )
        return picked / density
    raise CalcInputError("basis", "harvest.basis_invalid")


def kg_per_ha(kg: Decimal, area_ha: Decimal) -> Decimal:
    """Yield density from harvested mass and the covered area.

    kg_per_ha = kg / area_ha

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    mass = _require_positive(kg, "kg", "harvest.kg_must_be_positive")
    area = _require_positive(area_ha, "area_ha", "harvest.area_must_be_positive")
    return mass / area
