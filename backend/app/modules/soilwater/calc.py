"""Pure soil-water calculations. No database and no I/O."""

from decimal import Decimal
from typing import Literal

Feel = Literal["dry", "slightly_moist", "moist", "wet"]
SoilStatus = Literal["irrigate_soon", "ok"]

_FEEL_MIDDLE: dict[str, Decimal] = {
    "dry": Decimal("0.125"),
    "slightly_moist": Decimal("0.375"),
    "moist": Decimal("0.625"),
    "wet": Decimal("0.875"),
}


class CalcInputError(ValueError):
    """A soil-water input is zero, negative, or outside its allowed range."""

    def __init__(self, field: str, code: str) -> None:
        self.field = field
        self.code = code
        super().__init__(code)


def _positive_code(field: str) -> str:
    return f"soilwater.{field}_must_be_positive"


def _require_positive(value: Decimal, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise CalcInputError(field, _positive_code(field))
    return value


def _require_non_negative(value: Decimal, field: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise CalcInputError(field, _positive_code(field))
    return value


def _require_efficiency(efficiency: Decimal) -> Decimal:
    if (
        not isinstance(efficiency, Decimal)
        or not efficiency.is_finite()
        or efficiency <= 0
        or efficiency > 1
    ):
        raise CalcInputError("efficiency", "soilwater.efficiency_out_of_range")
    return efficiency


def taw_mm(theta_fc: Decimal, theta_wp: Decimal, root_depth_m: Decimal) -> Decimal:
    """Total available water in the root zone.

    taw_mm = 1000 × (theta_fc − theta_wp) × root_depth_m

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    fc = _require_positive(theta_fc, "theta_fc")
    wp = _require_positive(theta_wp, "theta_wp")
    depth = _require_positive(root_depth_m, "root_depth_m")
    return Decimal(1000) * (fc - wp) * depth


def raw_mm(p: Decimal, taw_mm: Decimal) -> Decimal:
    """Readily available water.

    raw_mm = p × taw_mm

    ``p`` is the depletion fraction, between 0 and 1.

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    fraction = _require_positive(p, "p")
    store = _require_positive(taw_mm, "taw_mm")
    return fraction * store


def water_left_mm(taw_mm: Decimal, dr_mm: Decimal) -> Decimal:
    """Water remaining in the root zone.

    water_left_mm = taw_mm − dr_mm

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    capacity = _require_positive(taw_mm, "taw_mm")
    depletion = _require_non_negative(dr_mm, "dr_mm")
    return capacity - depletion


def irrigate_below_mm(taw_mm: Decimal, raw_mm: Decimal) -> Decimal:
    """Water left at which irrigation is due.

    irrigate_below_mm = taw_mm − raw_mm

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    capacity = _require_positive(taw_mm, "taw_mm")
    readily = _require_non_negative(raw_mm, "raw_mm")
    return capacity - readily


def etc_mm(et0_mm: Decimal, kc: Decimal) -> Decimal:
    """Crop evapotranspiration for one day.

    etc_mm = et0_mm × kc

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    et0 = _require_positive(et0_mm, "et0_mm")
    coefficient = _require_positive(kc, "kc")
    return et0 * coefficient


def daily_balance(
    dr_prev_mm: Decimal,
    rain_mm: Decimal,
    irrigation_soil_mm: Decimal,
    etc_mm: Decimal,
    taw_mm: Decimal,
) -> tuple[Decimal, Decimal]:
    """End-of-day root-zone depletion and drainage above field capacity.

    unclamped = dr_prev_mm − rain_mm − irrigation_soil_mm + etc_mm
    if unclamped < 0: drainage_mm = −unclamped and dr_mm = 0
    elif unclamped > taw_mm: dr_mm = taw_mm and drainage_mm = 0
    else: dr_mm = unclamped and drainage_mm = 0

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    previous = _require_non_negative(dr_prev_mm, "dr_prev_mm")
    rain = _require_non_negative(rain_mm, "rain_mm")
    irrigation = _require_non_negative(irrigation_soil_mm, "irrigation_soil_mm")
    crop_et = _require_non_negative(etc_mm, "etc_mm")
    capacity = _require_positive(taw_mm, "taw_mm")
    unclamped = previous - rain - irrigation + crop_et
    if unclamped < 0:
        return Decimal(0), -unclamped
    if unclamped > capacity:
        return capacity, Decimal(0)
    return unclamped, Decimal(0)


def status(dr_mm: Decimal, raw_mm: Decimal) -> SoilStatus:
    """Irrigation timing from depletion and readily available water.

    status = irrigate_soon when dr_mm >= raw_mm, otherwise ok

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    depletion = _require_non_negative(dr_mm, "dr_mm")
    readily = _require_non_negative(raw_mm, "raw_mm")
    if depletion >= readily:
        return "irrigate_soon"
    return "ok"


def gross_mm(net_mm: Decimal, efficiency: Decimal) -> Decimal:
    """Gross irrigation depth that delivers a net depth at the given efficiency.

    gross_mm = net_mm / efficiency

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    net = _require_positive(net_mm, "net_mm")
    ratio = _require_efficiency(efficiency)
    return net / ratio


def run_time_min(gross_mm: Decimal, rate_mm_h: Decimal) -> Decimal:
    """Minutes a system must run to apply a gross depth.

    run_time_min = gross_mm / rate_mm_h × 60

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    gross = _require_positive(gross_mm, "gross_mm")
    rate = _require_positive(rate_mm_h, "rate_mm_h")
    return gross / rate * Decimal(60)


def volume_m3(q_m3h: Decimal, duration_min: Decimal) -> Decimal:
    """Volume applied by a flow over a run time.

    volume_m3 = q_m3h × duration_min / 60

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    flow = _require_positive(q_m3h, "q_m3h")
    duration = _require_positive(duration_min, "duration_min")
    return flow * duration / Decimal(60)


def depth_mm(rate_mm_h: Decimal, duration_min: Decimal) -> Decimal:
    """Depth applied by a precipitation rate over a run time.

    depth_mm = rate_mm_h × duration_min / 60

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    rate = _require_positive(rate_mm_h, "rate_mm_h")
    duration = _require_positive(duration_min, "duration_min")
    return rate * duration / Decimal(60)


def soil_entering(
    rate_mm_h: Decimal,
    duration_min: Decimal,
    efficiency: Decimal,
    infiltration_mm_h: Decimal | None = None,
) -> tuple[Decimal, Decimal]:
    """Depth that enters the soil, and depth that runs off.

    Without an infiltration rate: soil_mm = depth_mm × efficiency and runoff_mm = 0.
    With one: soil_mm = min(rate_mm_h, infiltration_mm_h) × duration_min / 60 × efficiency
    and runoff_mm = max(0, rate_mm_h − infiltration_mm_h) × duration_min / 60.

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    rate = _require_positive(rate_mm_h, "rate_mm_h")
    duration = _require_positive(duration_min, "duration_min")
    ratio = _require_efficiency(efficiency)
    hours = duration / Decimal(60)
    if infiltration_mm_h is None:
        return depth_mm(rate, duration) * ratio, Decimal(0)
    infiltration = _require_non_negative(infiltration_mm_h, "infiltration_mm_h")
    soil = min(rate, infiltration) * hours * ratio
    runoff = max(Decimal(0), rate - infiltration) * hours
    return soil, runoff


def soil_check_reset_mm(taw_mm: Decimal, feel: Feel) -> Decimal:
    """Depletion reset from a soil-feel check.

    soil_check_reset_mm = taw_mm × (1 − band middle)
    Band middles: dry 0.125, slightly_moist 0.375, moist 0.625, wet 0.875.

    Source: AGRECT system design, Calculation reference — Soil & water (FAO-56).
    """
    capacity = _require_positive(taw_mm, "taw_mm")
    middle = _FEEL_MIDDLE.get(feel)
    if middle is None:
        raise CalcInputError("feel", "soilwater.feel_invalid")
    return capacity * (Decimal(1) - middle)
