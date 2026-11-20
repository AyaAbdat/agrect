from datetime import date
from decimal import Decimal

import pytest

from app.modules.weather.calc import (
    CalendarDayTemps,
    average_by_calendar_day,
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


def _temps(day: date, tmin: str | None, tmax: str | None) -> CalendarDayTemps:
    return CalendarDayTemps(
        day=day,
        tmin_c=None if tmin is None else D(tmin),
        tmax_c=None if tmax is None else D(tmax),
    )


def test_average_by_calendar_day_including_29_february() -> None:
    rows = [
        _temps(date(2024, 2, 29), "1", "11"),
        _temps(date(2024, 2, 28), "9", "19"),
        _temps(date(2023, 2, 28), "3", "13"),
        _temps(date(2021, 2, 28), None, "15"),
        _temps(date(2020, 3, 15), "4", "14"),
        _temps(date(2021, 3, 15), "6", "16"),
    ]
    leap = average_by_calendar_day(rows, 2, 29)
    assert leap.tmin_c == Decimal("2")
    assert leap.tmax_c == Decimal("13")
    march = average_by_calendar_day(rows, 3, 15)
    assert march.tmin_c == Decimal("5")
    assert march.tmax_c == Decimal("15")
    assert average_by_calendar_day([], 3, 15).tmin_c is None
    assert average_by_calendar_day([], 3, 15).tmax_c is None


def test_dewpoint_and_hour_counts() -> None:
    assert isinstance(dewpoint_c(D("25"), D("50")), Decimal)
    assert_matches(dewpoint_c(D("25"), D("50")), "13.9")
    temps = [D("-1"), D("0"), D("3.5"), D("7.2"), D("7.3")]
    assert chill_hours(temps) == 3
    assert count_hours_at_or_below([D("-1"), D("0"), D("1")], D("0")) == 2
