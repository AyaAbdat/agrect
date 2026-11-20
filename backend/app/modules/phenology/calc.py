"""Pure phenology predictions. No database and no I/O.

Degree days are cumulative from the season start. An observed stage is a fact
and re-anchors every later stage. Nothing in this module invents a target,
a base temperature, or a date.
"""

import calendar
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

DayKind = Literal["observed_weather", "forecast", "average"]
StageLabel = Literal["observed", "predicted", "not_enough_data", "beyond_data"]
SeriesPoint = tuple[date, Decimal, DayKind]

_RANGE_YEARS = 3


@dataclass(frozen=True, slots=True)
class StageCall[S]:
    stage_id: S
    label: StageLabel
    date: date | None
    dd_needed: Decimal | None
    dd_counted: Decimal
    anchor_stage_id: S | None


@dataclass(frozen=True, slots=True)
class StageWindow[S]:
    stage_id: S
    earliest: date | None
    latest: date | None


def counted_through(series: Sequence[SeriesPoint], day: date) -> Decimal:
    """Running degree-day total on series days on or before ``day``.

    total(day) = Σ gdd(d) for d in series where d <= day

    Days with no series row contribute nothing. The total before the first
    series day is 0.

    Source: AGRECT system design — Crop growth model, steps 1–5.
    """
    days, totals = _accumulate(series)
    return _total_on_or_before(days, totals, day)


def predict[S](
    season_start: date,
    series: Sequence[SeriesPoint],
    stages: Sequence[tuple[S, int, Decimal | None]],
    observations: Mapping[S, date],
    *,
    today: date,
) -> list[StageCall[S]]:
    """Predict one date per stage, or refuse when the target cannot be met.

    The running total starts at 0 before ``season_start`` and adds each series
    day's degree days. ``dd_needed`` is the cumulative target from the season
    start.

    - An observed stage is a fact: its date is the observation.
    - A stage with ``dd_needed`` None is ``not_enough_data``.
    - Otherwise the latest earlier observed stage ``k`` re-anchors stage ``j``:
      the predicted date is the first series day after the observation where
      the degree days counted since that observation are at least
      ``dd_j − dd_k``. When ``dd_k`` is None, counting stays on the
      season-start total.
    - With no anchor, the predicted date is the first series day whose running
      total is at least ``dd_needed``.
    - When no series day reaches the target, the label is ``beyond_data``.

    ``dd_counted`` is the running total on the stage date, or through ``today``
    when the stage has no date. ``season_start`` is the origin of the total;
    series rows before it still count if the caller included them.

    Source: AGRECT system design — Crop growth model, steps 1–5.
    """
    days, totals = _accumulate(series)
    ordered = sorted(stages, key=lambda item: (item[1], _stage_key(item[0])))
    results: list[StageCall[S]] = []
    anchor: tuple[S, Decimal | None, date] | None = None
    for stage_id, _sort, dd_needed in ordered:
        observed_on = observations.get(stage_id)
        if observed_on is not None:
            results.append(
                StageCall(
                    stage_id=stage_id,
                    label="observed",
                    date=observed_on,
                    dd_needed=dd_needed,
                    dd_counted=_total_on_or_before(days, totals, observed_on),
                    anchor_stage_id=None,
                )
            )
            anchor = (stage_id, dd_needed, observed_on)
            continue
        if dd_needed is None:
            results.append(
                _undated(
                    stage_id,
                    "not_enough_data",
                    dd_needed,
                    _total_on_or_before(days, totals, today),
                )
            )
            continue
        found, anchor_id = _predicted_day(days, totals, dd_needed, anchor)
        if found is None:
            results.append(
                _undated(
                    stage_id,
                    "beyond_data",
                    dd_needed,
                    _total_on_or_before(days, totals, today),
                )
            )
            continue
        results.append(
            StageCall(
                stage_id=stage_id,
                label="predicted",
                date=found,
                dd_needed=dd_needed,
                dd_counted=_total_on_or_before(days, totals, found),
                anchor_stage_id=anchor_id,
            )
        )
    return results


def predict_range[S](
    season_start: date,
    series: Sequence[SeriesPoint],
    stages: Sequence[tuple[S, int, Decimal | None]],
    observations: Mapping[S, date],
    years: Sequence[Mapping[date, Decimal]],
    *,
    today: date,
) -> list[StageWindow[S]]:
    """Earliest and latest predicted dates across past years.

    Each year replaces only the ``average`` days of ``series`` with that
    year's degree days on the same calendar day. 29 February uses 29 February
    in a leap year and 28 February otherwise. Observed-weather and forecast
    days stay as they are. ``predict`` then runs once per year.

    earliest = min(predicted dates), latest = max(predicted dates). Both are
    null when fewer than 3 years were supplied or fewer than 3 of them
    produced a predicted date for that stage. Observed stages are facts, so
    they have no range.

    Source: AGRECT system design — Crop growth model, steps 1–5.
    """
    ordered = sorted(stages, key=lambda item: (item[1], _stage_key(item[0])))
    stage_ids = [stage_id for stage_id, _sort, _dd in ordered]
    if len(years) < _RANGE_YEARS:
        return [
            StageWindow(stage_id=stage_id, earliest=None, latest=None) for stage_id in stage_ids
        ]
    found: dict[S, list[date]] = {stage_id: [] for stage_id in stage_ids}
    for year_gdd in years:
        replaced = _replace_average(series, year_gdd)
        for row in predict(
            season_start,
            replaced,
            ordered,
            observations,
            today=today,
        ):
            if row.label == "predicted" and row.date is not None:
                found[row.stage_id].append(row.date)
    windows: list[StageWindow[S]] = []
    for stage_id in stage_ids:
        dates = found[stage_id]
        if len(dates) < _RANGE_YEARS:
            windows.append(StageWindow(stage_id=stage_id, earliest=None, latest=None))
            continue
        windows.append(StageWindow(stage_id=stage_id, earliest=min(dates), latest=max(dates)))
    return windows


def _predicted_day[S](
    days: Sequence[date],
    totals: Mapping[date, Decimal],
    dd_needed: Decimal,
    anchor: tuple[S, Decimal | None, date] | None,
) -> tuple[date | None, S | None]:
    """First day the remaining target is met, and the anchor that set it."""
    if anchor is not None and anchor[1] is not None:
        anchor_id, anchor_dd, anchor_on = anchor
        base = _total_on_or_before(days, totals, anchor_on)
        return _first_after(days, totals, anchor_on, base, dd_needed - anchor_dd), anchor_id
    return _first_reaching(days, totals, dd_needed), None


def _undated[S](
    stage_id: S,
    label: StageLabel,
    dd_needed: Decimal | None,
    dd_counted: Decimal,
) -> StageCall[S]:
    return StageCall(
        stage_id=stage_id,
        label=label,
        date=None,
        dd_needed=dd_needed,
        dd_counted=dd_counted,
        anchor_stage_id=None,
    )


def _accumulate(
    series: Sequence[SeriesPoint],
) -> tuple[list[date], dict[date, Decimal]]:
    ordered: dict[date, Decimal] = {}
    for day, gdd, _kind in series:
        ordered[day] = gdd
    days = sorted(ordered)
    totals: dict[date, Decimal] = {}
    running = Decimal(0)
    for day in days:
        running += ordered[day]
        totals[day] = running
    return days, totals


def _total_on_or_before(
    days: Sequence[date],
    totals: Mapping[date, Decimal],
    day: date,
) -> Decimal:
    total = Decimal(0)
    for item in days:
        if item > day:
            break
        total = totals[item]
    return total


def _first_reaching(
    days: Sequence[date],
    totals: Mapping[date, Decimal],
    needed: Decimal,
) -> date | None:
    for day in days:
        if totals[day] >= needed:
            return day
    return None


def _first_after(
    days: Sequence[date],
    totals: Mapping[date, Decimal],
    after: date,
    base: Decimal,
    needed: Decimal,
) -> date | None:
    for day in days:
        if day <= after:
            continue
        if totals[day] - base >= needed:
            return day
    return None


def _replace_average(
    series: Sequence[SeriesPoint],
    year_gdd: Mapping[date, Decimal],
) -> list[SeriesPoint]:
    replaced: list[SeriesPoint] = []
    for day, gdd, kind in series:
        if kind != "average":
            replaced.append((day, gdd, kind))
            continue
        value = _lookup_year_gdd(year_gdd, day)
        if value is None:
            continue
        replaced.append((day, value, "average"))
    return replaced


def _lookup_year_gdd(year_gdd: Mapping[date, Decimal], day: date) -> Decimal | None:
    """Degree days on the same calendar day in one past year.

    29 February matches 29 February when that year has it, and 28 February
    when the past year is not a leap year.
    """
    exact: Decimal | None = None
    february_28: Decimal | None = None
    for item, value in year_gdd.items():
        if item.month == day.month and item.day == day.day:
            exact = value
            break
        if (
            february_28 is None
            and day.month == 2
            and day.day == 29
            and item.month == 2
            and item.day == 28
            and not calendar.isleap(item.year)
        ):
            february_28 = value
    if exact is not None:
        return exact
    return february_28


def _stage_key(stage_id: object) -> str:
    return str(stage_id)
