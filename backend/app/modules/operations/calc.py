"""Pure field-operation calculations. No database and no I/O."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Literal

RateBasis = Literal["per_ha", "per_100l", "per_block"]


class CalcInputError(ValueError):
    """An operation input is missing, zero, or outside its allowed range."""

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


def area_worked_ha(
    net_area_ha: Decimal,
    valve_areas_ha: Sequence[Decimal] | None = None,
) -> Decimal:
    """Net planted area (ha) covered by one field operation.

    When valve_areas_ha is None or empty -> net_area_ha (whole block).
    When valves are chosen -> Σ valve_areas_ha.

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    if valve_areas_ha:
        total = Decimal(0)
        for area in valve_areas_ha:
            total += _require_positive(area, "valve_areas_ha", "operations.valve_area_required")
        return total
    return _require_positive(net_area_ha, "net_area_ha", "operations.net_area_required")


def product_total(
    rate: Decimal,
    rate_basis: RateBasis,
    area_ha: Decimal,
    water_l_ha: Decimal | None = None,
) -> Decimal:
    """Total product quantity for one operation line (same unit as rate).

    per_ha -> rate × area_ha
    per_100l -> rate × water_l_ha × area_ha / 100  (water_l_ha required)
    per_block -> rate

    Work in the rate unit (e.g. mL); convert only for display. Unit is kept.

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    amount = _require_positive(rate, "rate", "operations.rate_must_be_positive")
    if rate_basis == "per_ha":
        area = _require_positive(area_ha, "area_ha", "operations.area_must_be_positive")
        return amount * area
    if rate_basis == "per_100l":
        if water_l_ha is None:
            raise CalcInputError("water_l_ha", "operations.water_required")
        water = _require_positive(water_l_ha, "water_l_ha", "operations.water_required")
        area = _require_positive(area_ha, "area_ha", "operations.area_must_be_positive")
        return amount * water * area / Decimal(100)
    if rate_basis == "per_block":
        return amount
    raise CalcInputError("rate_basis", "operations.rate_basis_invalid")


def nutrient_applied_kg_ha(product_kg_ha: Decimal, content_fraction: Decimal) -> Decimal:
    """Nutrient applied from a product rate and its content fraction.

    nutrient_kg_ha = product_kg_ha × content_fraction

    content_fraction is the nutrient share as a fraction (e.g. 0.15 for 15 %).

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    rate = _require_finite(product_kg_ha, "product_kg_ha", "operations.product_kg_ha_invalid")
    if rate < 0:
        raise CalcInputError("product_kg_ha", "operations.product_kg_ha_invalid")
    fraction = _require_finite(
        content_fraction,
        "content_fraction",
        "operations.content_fraction_invalid",
    )
    if fraction < 0:
        raise CalcInputError("content_fraction", "operations.content_fraction_invalid")
    return rate * fraction


def preharvest_ok(
    harvest_date: date,
    last_spray_date: date,
    phi_days: int,
) -> tuple[bool, int, int]:
    """Whether a harvest falls outside a product's pre-harvest interval.

    days_since = harvest_date − last_spray_date (calendar days).
    ok when days_since >= phi_days; warn when days_since < phi_days.
    Equal days is ok (boundary).

    Source: AGRECT system design — Calculation reference, Registry and record modules.
    """
    if phi_days < 0:
        raise CalcInputError("phi_days", "operations.phi_invalid")
    days_since = (harvest_date - last_spray_date).days
    return days_since >= phi_days, days_since, phi_days
