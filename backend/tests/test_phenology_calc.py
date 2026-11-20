from datetime import date, timedelta
from decimal import Decimal

from app.modules.phenology.calc import counted_through, predict, predict_range

_START = date(2026, 1, 1)


def _series(days: int, gdd: str, *, kind: str = "observed_weather", start: date = _START):
    return [(start + timedelta(days=offset), Decimal(gdd), kind) for offset in range(days)]


def test_constant_ten_reaches_one_hundred_on_day_10() -> None:
    series = _series(30, "10")
    today = _START
    rows = predict(
        _START,
        series,
        [("bud", 1, Decimal("100"))],
        {},
        today=today,
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.label == "predicted"
    assert row.date == date(2026, 1, 10)
    assert row.dd_needed == Decimal("100")
    assert row.dd_counted == Decimal("100")
    assert row.anchor_stage_id is None
    assert counted_through(series, today) == Decimal("10")


def test_earlier_observation_moves_later_stages_by_the_same_amount() -> None:
    series = _series(40, "10")
    stages = [
        ("a", 1, Decimal("100")),
        ("b", 2, Decimal("200")),
    ]
    plain = predict(_START, series, stages, {}, today=_START)
    assert plain[0].date == date(2026, 1, 10)
    assert plain[1].date == date(2026, 1, 20)
    observed_on = date(2026, 1, 6)
    moved = predict(_START, series, stages, {"a": observed_on}, today=_START)
    assert moved[0].label == "observed"
    assert moved[0].date == observed_on
    assert moved[0].dd_counted == Decimal("60")
    assert moved[0].anchor_stage_id is None
    assert moved[1].label == "predicted"
    assert moved[1].date == date(2026, 1, 16)
    assert moved[1].anchor_stage_id == "a"
    assert moved[1].dd_needed == Decimal("200")
    assert moved[1].dd_counted == Decimal("160")
    assert (plain[1].date - moved[1].date) == (plain[0].date - observed_on)


def test_missing_anchor_degree_days_fall_back_to_season_start() -> None:
    series = _series(20, "10")
    rows = predict(
        _START,
        series,
        [("a", 1, None), ("b", 2, Decimal("100"))],
        {"a": date(2026, 1, 2)},
        today=_START,
    )
    assert rows[0].label == "observed"
    assert rows[1].label == "predicted"
    assert rows[1].date == date(2026, 1, 10)
    assert rows[1].anchor_stage_id is None


def test_missing_degree_days_are_not_enough_data() -> None:
    rows = predict(
        _START,
        _series(15, "10"),
        [("a", 1, None)],
        {},
        today=_START,
    )
    assert rows[0].label == "not_enough_data"
    assert rows[0].date is None
    assert rows[0].dd_needed is None
    assert rows[0].dd_counted == Decimal("10")


def test_target_never_reached_is_beyond_data() -> None:
    series = _series(5, "10")
    today = _START + timedelta(days=2)
    rows = predict(
        _START,
        series,
        [("a", 1, Decimal("100"))],
        {},
        today=today,
    )
    assert rows[0].label == "beyond_data"
    assert rows[0].date is None
    assert rows[0].dd_counted == Decimal("30")
    assert counted_through(series, today) == Decimal("30")


def test_range_over_three_years_is_min_and_max() -> None:
    start = date(2026, 6, 1)
    series = []
    for offset in range(5):
        series.append((start + timedelta(days=offset), Decimal("0"), "observed_weather"))
    series.append((start + timedelta(days=5), Decimal("0"), "forecast"))
    for offset in range(6, 40):
        series.append((start + timedelta(days=offset), Decimal("1"), "average"))

    def year_map(year: int, rate: str) -> dict[date, Decimal]:
        return {date(year, 6, 1) + timedelta(days=offset): Decimal(rate) for offset in range(40)}

    windows = predict_range(
        start,
        series,
        [("flower", 1, Decimal("30"))],
        {},
        [year_map(2023, "10"), year_map(2022, "15"), year_map(2021, "30")],
        today=start,
    )
    assert windows[0].earliest == date(2026, 6, 7)
    assert windows[0].latest == date(2026, 6, 9)
    short = predict_range(
        start,
        series,
        [("flower", 1, Decimal("30"))],
        {},
        [year_map(2023, "10"), year_map(2022, "15")],
        today=start,
    )
    assert short[0].earliest is None
    assert short[0].latest is None


def test_leap_day_uses_29_february_or_28_february() -> None:
    start = date(2024, 2, 28)
    series = [
        (date(2024, 2, 28), Decimal("0"), "average"),
        (date(2024, 2, 29), Decimal("0"), "average"),
        (date(2024, 3, 1), Decimal("0"), "average"),
    ]

    def non_leap(year: int) -> dict[date, Decimal]:
        return {date(year, 2, 28): Decimal("10"), date(year, 3, 1): Decimal("0")}

    fell_back = predict_range(
        start,
        series,
        [("bud", 1, Decimal("15"))],
        {},
        [non_leap(2023), non_leap(2022), non_leap(2021)],
        today=start,
    )
    assert fell_back[0].earliest == date(2024, 2, 29)
    assert fell_back[0].latest == date(2024, 2, 29)

    def leap(year: int) -> dict[date, Decimal]:
        return {date(year, 2, 28): Decimal("3"), date(year, 2, 29): Decimal("7")}

    exact = predict_range(
        date(2024, 2, 29),
        [(date(2024, 2, 29), Decimal("0"), "average")],
        [("bud", 1, Decimal("7"))],
        {},
        [leap(2020), leap(2016), leap(2012)],
        today=date(2024, 2, 29),
    )
    assert exact[0].earliest == date(2024, 2, 29)
    assert exact[0].latest == date(2024, 2, 29)
