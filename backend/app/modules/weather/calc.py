"""Pure weather calculations. No database and no I/O.

Single-sine trigonometry uses Python ``math`` on floats because ``Decimal`` has
no trig functions (D-046). Inputs and outputs stay ``Decimal``, and the
single-sine result is quantized to 0.0001 °C·day.
"""

import math
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

# FAO-56 equation 11 (Tetens / Magnus) constants.
_ES_COEF = Decimal("0.6108")
_MAGNUS_A = Decimal("17.27")
_MAGNUS_B = Decimal("237.3")

# Weinberger chill-hour bounds: 0 °C through 7.2 °C (45 °F).
_CHILL_MIN_C = Decimal("0")
_CHILL_MAX_C = Decimal("7.2")

_GDD_QUANTUM = Decimal("0.0001")


def es_kpa(temp_c: Decimal) -> Decimal:
    """Saturation vapour pressure.

    es = 0.6108 × exp(17.27 × T / (T + 237.3))

    Source: FAO Irrigation and Drainage Paper 56, equation 11.
    """
    exponent = (_MAGNUS_A * temp_c) / (temp_c + _MAGNUS_B)
    return _ES_COEF * exponent.exp()


def ea_kpa(temp_c: Decimal, rh_pct: Decimal) -> Decimal:
    """Actual vapour pressure.

    ea = es(T) × RH / 100

    Source: FAO Irrigation and Drainage Paper 56, equation 17
    (saturation vapour pressure scaled by relative humidity).
    """
    return es_kpa(temp_c) * rh_pct / Decimal(100)


def vpd_kpa(temp_c: Decimal, rh_pct: Decimal) -> Decimal:
    """Vapour pressure deficit.

    vpd = es(T) − ea(T, RH)

    Source: FAO Irrigation and Drainage Paper 56, equation 11 minus
    actual vapour pressure.
    """
    return es_kpa(temp_c) - ea_kpa(temp_c, rh_pct)


def dewpoint_c(temp_c: Decimal, rh_pct: Decimal) -> Decimal:
    """Dew-point temperature.

    gamma = ln(RH / 100) + 17.27 × T / (T + 237.3)
    Td = 237.3 × gamma / (17.27 − gamma)

    Source: Magnus formula with the FAO-56 equation 11 constants.
    """
    gamma = (rh_pct / Decimal(100)).ln() + (_MAGNUS_A * temp_c) / (temp_c + _MAGNUS_B)
    return (_MAGNUS_B * gamma) / (_MAGNUS_A - gamma)


def gdd_average(
    tmax_c: Decimal,
    tmin_c: Decimal,
    base_c: Decimal,
    upper_c: Decimal | None = None,
) -> Decimal:
    """Average-method growing degree-days.

    gdd = max(0, (min(tmax, upper) + tmin) / 2 − base)

    ``upper`` caps maximum temperature only. When it is omitted, tmax is used
    unchanged.

    Source: AGRECT system design, weather degree-days (average method).
    """
    capped_max = tmax_c if upper_c is None else min(tmax_c, upper_c)
    raw = (capped_max + tmin_c) / Decimal(2) - base_c
    if raw < 0:
        return Decimal(0)
    return raw


def _quantize_gdd(value: Decimal) -> Decimal:
    return value.quantize(_GDD_QUANTUM, rounding=ROUND_HALF_UP)


def _theta(limit_c: Decimal, mean_c: Decimal, half_c: Decimal) -> float:
    ratio = (float(limit_c) - float(mean_c)) / float(half_c)
    if ratio > 1.0:
        ratio = 1.0
    elif ratio < -1.0:
        ratio = -1.0
    return math.asin(ratio)


def _from_trig(value: float) -> Decimal:
    """Quantize a float trig result to 0.0001 °C·day (D-046)."""
    return _quantize_gdd(Decimal(str(value)))


def gdd_single_sine(
    tmax_c: Decimal,
    tmin_c: Decimal,
    base_c: Decimal,
    upper_c: Decimal | None = None,
) -> Decimal:
    """Single-sine growing degree-days with a horizontal upper cutoff.

    M = (tmax + tmin) / 2 and W = (tmax − tmin) / 2.

    - tmax <= base -> 0
    - upper set and tmin >= upper -> upper − base
    - tmin >= base and (no upper or tmax <= upper) -> M − base
    - tmin < base and (no upper or tmax <= upper):
      θ1 = asin((base − M) / W)
      DD = ((M − base) (π/2 − θ1) + W cos θ1) / π
    - tmin >= base and tmax > upper:
      θ2 = asin((upper − M) / W)
      DD = ((M − base) (θ2 + π/2) + (upper − base) (π/2 − θ2) − W cos θ2) / π
    - tmin < base and tmax > upper:
      DD = ((M − base) (θ2 − θ1) + W (cos θ1 − cos θ2)
            + (upper − base) (π/2 − θ2)) / π

    Angles use ``math`` on floats. The returned degree-days are ``Decimal``,
    quantized to 0.0001 with ROUND_HALF_UP (D-046).

    Source: Zalom et al. (1983) / UC IPM single-sine method, horizontal cutoff.
    """
    if tmax_c <= base_c:
        return _quantize_gdd(Decimal(0))
    if upper_c is not None and tmin_c >= upper_c:
        return _quantize_gdd(upper_c - base_c)
    mean = (tmax_c + tmin_c) / Decimal(2)
    half = (tmax_c - tmin_c) / Decimal(2)
    below_upper = upper_c is None or tmax_c <= upper_c
    if tmin_c >= base_c and below_upper:
        return _quantize_gdd(mean - base_c)
    if half == 0:
        return _quantize_gdd(max(mean - base_c, Decimal(0)))
    if tmin_c < base_c and below_upper:
        theta_1 = _theta(base_c, mean, half)
        width = float(half)
        dd = (
            (float(mean - base_c)) * (math.pi / 2 - theta_1) + width * math.cos(theta_1)
        ) / math.pi
        return _from_trig(dd)
    if upper_c is None:
        return _quantize_gdd(max(mean - base_c, Decimal(0)))
    theta_2 = _theta(upper_c, mean, half)
    width = float(half)
    if tmin_c >= base_c:
        dd = (
            (float(mean - base_c)) * (theta_2 + math.pi / 2)
            + (float(upper_c - base_c)) * (math.pi / 2 - theta_2)
            - width * math.cos(theta_2)
        ) / math.pi
        return _from_trig(dd)
    theta_1 = _theta(base_c, mean, half)
    dd = (
        (float(mean - base_c)) * (theta_2 - theta_1)
        + width * (math.cos(theta_1) - math.cos(theta_2))
        + (float(upper_c - base_c)) * (math.pi / 2 - theta_2)
    ) / math.pi
    return _from_trig(dd)


_RAD_HOUR_J = Decimal(3600)
_J_PER_CM2 = Decimal(10000)
_RAD_QUANTUM = Decimal("0.01")


def radiation_sum_jcm2(values_wm2: Sequence[Decimal]) -> Decimal:
    """Sum hourly irradiance into joules per square centimetre.

    sum = Σ (rad_W/m² × 3600 / 10 000)

    One watt per square metre for one hour is 3600 J/m², and 1 J/cm² is
    10 000 J/m². The result is quantized to 0.01 J/cm² with ROUND_HALF_UP.

    Source: AGRECT weather strip, hourly shortwave radiation over the local
    day so far.
    """
    total = sum((value * _RAD_HOUR_J / _J_PER_CM2 for value in values_wm2), Decimal(0))
    return total.quantize(_RAD_QUANTUM, rounding=ROUND_HALF_UP)


def count_hours_at_or_below(temps: Sequence[Decimal], threshold: Decimal) -> int:
    """Count temperatures at or below a threshold.

    count = |{T in temps : T <= threshold}|

    Source: AGRECT farm frost hours (threshold is the grower-entered frost setting).
    """
    return sum(1 for temp in temps if temp <= threshold)


def count_hours_at_or_above(temps: Sequence[Decimal], threshold: Decimal) -> int:
    """Count temperatures at or above a threshold.

    count = |{T in temps : T >= threshold}|

    Source: AGRECT farm heat hours (threshold is the grower-entered heat setting).
    """
    return sum(1 for temp in temps if temp >= threshold)


def chill_hours(temps: Sequence[Decimal]) -> int:
    """Count chill hours.

    count = |{T in temps : 0 <= T <= 7.2}|

    Source: Weinberger (1950) chill hours, 32–45 °F (0–7.2 °C).
    """
    return sum(1 for temp in temps if _CHILL_MIN_C <= temp <= _CHILL_MAX_C)
