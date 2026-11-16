from decimal import Decimal

import pytest

from app.modules.weather.calc import (
    chill_hours,
    count_hours_at_or_below,
    dewpoint_c,
    es_kpa,
    gdd_average,
    gdd_single_sine,
    radiation_sum_jcm2,
    vpd_kpa,
)
from tests.vectors import D, VectorCase, assert_matches, load


@pytest.mark.parametrize("case", load("weather"), ids=lambda case: case["id"])
def test_weather_vector(case: VectorCase) -> None:
    raw = case["input"]
    expected = case["expected"]
    if case["id"] == "weather.vpd":
        es = es_kpa(D(raw["temp_c"]))
        deficit = vpd_kpa(D(raw["temp_c"]), D(raw["rh_pct"]))
        assert isinstance(es, Decimal)
        assert isinstance(deficit, Decimal)
        assert_matches(es, expected["es_kpa"])
        assert_matches(deficit, expected["vpd_kpa"])
    elif case["id"] == "weather.gdd_average":
        actual = gdd_average(D(raw["tmax_c"]), D(raw["tmin_c"]), D(raw["base_c"]))
        assert isinstance(actual, Decimal)
        assert_matches(actual, expected["gdd_cd"])
    elif case["id"] == "weather.gdd_average_upper":
        actual = gdd_average(
            D(raw["tmax_c"]),
            D(raw["tmin_c"]),
            D(raw["base_c"]),
            D(raw["upper_c"]),
        )
        assert_matches(actual, expected["gdd_cd"])
    else:
        raise AssertionError(case["id"])


def test_single_sine_cases() -> None:
    assert_matches(gdd_single_sine(D("30"), D("14"), D("10")), "12.00")
    assert_matches(gdd_single_sine(D("30"), D("14"), D("10"), D("28")), "11.70")
    assert_matches(gdd_single_sine(D("20"), D("0"), D("10")), "3.18")
    assert_matches(gdd_single_sine(D("8"), D("2"), D("10")), "0.00")
    assert_matches(gdd_single_sine(D("35"), D("30"), D("10"), D("28")), "18.00")


def test_radiation_sum_jcm2() -> None:
    assert_matches(radiation_sum_jcm2([D("100"), D("200")]), "108.00")


def test_dewpoint_and_hour_counts() -> None:
    assert isinstance(dewpoint_c(D("25"), D("50")), Decimal)
    assert_matches(dewpoint_c(D("25"), D("50")), "13.9")
    temps = [D("-1"), D("0"), D("3.5"), D("7.2"), D("7.3")]
    assert chill_hours(temps) == 3
    assert count_hours_at_or_below([D("-1"), D("0"), D("1")], D("0")) == 2
