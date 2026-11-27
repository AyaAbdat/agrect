"""Pure inputs-and-cost calculations. No database and no I/O.

Source: AGRECT system design — Inputs and cost.
"""

from decimal import Decimal

# Unit families: a quantity converts only inside its family. The factor is the
# number of base units in one of this unit (base = g for mass, mL for volume).
_FAMILY = {
    "kg": "mass",
    "g": "mass",
    "l": "volume",
    "ml": "volume",
    "unit": "count",
}
_PER_BASE = {
    "kg": Decimal(1000),
    "g": Decimal(1),
    "l": Decimal(1000),
    "ml": Decimal(1),
    "unit": Decimal(1),
}


class CalcInputError(ValueError):
    """An inputs-and-cost input is missing, non-finite, or incompatible."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(code)


def _require_finite(value: Decimal, field: str, code: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CalcInputError(field, code)
    return value


def convert_qty(qty: Decimal, from_unit: str, to_unit: str) -> Decimal:
    """Convert a quantity between compatible units.

    kg <-> g and l <-> ml convert by a factor of 1000; a unit converts only to
    itself. Converting between different families (e.g. kg -> l) raises
    ``CalcInputError`` with code ``inputs.unit_mismatch``.

    Source: AGRECT system design — Inputs and cost.
    """
    amount = _require_finite(qty, "qty", "inputs.qty_invalid")
    if from_unit == to_unit:
        return amount
    if from_unit not in _FAMILY or to_unit not in _FAMILY:
        raise CalcInputError("unit", "inputs.unit_mismatch")
    if _FAMILY[from_unit] != _FAMILY[to_unit]:
        raise CalcInputError("unit", "inputs.unit_mismatch")
    return amount * _PER_BASE[from_unit] / _PER_BASE[to_unit]


def units_compatible(from_unit: str, to_unit: str) -> bool:
    """Whether ``from_unit`` can convert to ``to_unit`` (same unit or family).

    Source: AGRECT system design — Inputs and cost.
    """
    if from_unit == to_unit:
        return True
    if from_unit not in _FAMILY or to_unit not in _FAMILY:
        return False
    return _FAMILY[from_unit] == _FAMILY[to_unit]


def line_cost(qty: Decimal, price_per_unit: Decimal) -> Decimal:
    """Cost of a quantity at a unit price = qty × price_per_unit.

    Source: AGRECT system design — Inputs and cost.
    """
    amount = _require_finite(qty, "qty", "inputs.qty_invalid")
    price = _require_finite(price_per_unit, "price_per_unit", "inputs.price_invalid")
    return amount * price


def cost_per_ha(total_dzd: Decimal, net_area_ha: Decimal) -> Decimal:
    """Cost per hectare = total_dzd / net_area_ha (net area must be positive).

    Source: AGRECT system design — Inputs and cost.
    """
    total = _require_finite(total_dzd, "total_dzd", "inputs.total_invalid")
    area = _require_finite(net_area_ha, "net_area_ha", "inputs.area_must_be_positive")
    if area <= 0:
        raise CalcInputError("net_area_ha", "inputs.area_must_be_positive")
    return total / area


def water_cost(volume_m3: Decimal, price_per_m3: Decimal) -> Decimal:
    """Cost of irrigation water = volume_m3 × price_per_m3.

    Source: AGRECT system design — Inputs and cost.
    """
    volume = _require_finite(volume_m3, "volume_m3", "inputs.volume_invalid")
    price = _require_finite(price_per_m3, "price_per_m3", "inputs.price_invalid")
    return volume * price
