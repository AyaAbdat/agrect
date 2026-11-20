"""Block-season phenology: facts stay observed, the rest is predicted.

Stage degree days follow the catalogue read: the farm's entered value, then a
cited global value. A value is used only when its base, upper threshold
(both null or equal) and method match the block's effective GDD setting
(block override, otherwise the crop setting). Recompute is idempotent and
stays in the caller's transaction.
"""

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import publish, subscribe
from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop, StageDd, StageDef
from app.modules.farms.models import Farm
from app.modules.phenology import calc
from app.modules.phenology.calc import SeriesPoint
from app.modules.phenology.models import (
    BlockSeason,
    PredictionLabel,
    SeasonStatus,
    StageObservation,
    StagePrediction,
)
from app.modules.phenology.schemas import (
    BlockStagesOut,
    DdSource,
    HistoryOut,
    HistoryStatus,
    ObservationIn,
    ObservationItemOut,
    ObservationOut,
    SeasonOut,
    SeasonPut,
    SettingOut,
    StageBrief,
    StageRowOut,
    StageSummaryOut,
    SummaryBlockOut,
    SummaryNextOut,
    TodayOut,
)
from app.modules.registry.models import Block
from app.modules.weather.calc import (
    CalendarDayTemps,
    average_by_calendar_day,
    gdd_average,
    gdd_single_sine,
)
from app.modules.weather.models import EffectiveGddSetting, GddMethod, HistoryDaily, WeatherDaily
from app.modules.weather.service import effective_gdd_setting, ensure_history, history_years

_HORIZON_DAYS = 365
_NO_SETTING = "phenology.no_gdd_setting"
_MISMATCH = "phenology.setting_mismatch"
_NO_START = "phenology.season_start_required"
_History = HistoryStatus


@dataclass(frozen=True, slots=True)
class _Target:
    dd: Decimal | None
    source: DdSource | None
    citation: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class _StageView:
    stage_id: uuid.UUID
    code: str
    sort: int
    name_fr: str
    name_ar: str
    name_en: str
    label: PredictionLabel
    on: date | None
    earliest: date | None
    latest: date | None
    dd_needed: Decimal | None
    dd_counted: Decimal | None
    dd_source: DdSource | None
    citation: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class _View:
    season_id: uuid.UUID
    block_id: uuid.UUID
    farm_id: uuid.UUID
    year: int
    start_date: date | None
    start_stage_def_id: uuid.UUID | None
    start_observed: bool
    status: SeasonStatus
    setting: EffectiveGddSetting | None
    history_status: _History
    today: date
    today_dd: Decimal | None
    years_count: int
    observations: list[StageObservation]
    stages: list[_StageView]


def write_season(db: Session, block: Block, year: int, body: SeasonPut) -> SeasonOut:
    """Create or replace the season start. Exactly one of date or stage."""
    has_date = body.start_date is not None
    has_stage = body.start_stage_def_id is not None
    if has_date == has_stage:
        raise AppError("validation_error", 422, {"start_date": _NO_START})
    if body.start_stage_def_id is not None:
        _require_stage(db, block, body.start_stage_def_id, "start_stage_def_id")
    season = _find_season(db, block.id, year)
    if season is None:
        season = BlockSeason(
            farm_id=block.farm_id,
            block_id=block.id,
            year=year,
            status=SeasonStatus.open,
            start_observed=False,
        )
        db.add(season)
        db.flush()
    if body.start_date is not None:
        season.start_date = body.start_date
        season.start_stage_def_id = None
        season.start_observed = False
    else:
        season.start_stage_def_id = body.start_stage_def_id
        observed = _observation(db, season.id, body.start_stage_def_id)
        if observed is None:
            season.start_date = None
            season.start_observed = False
        else:
            season.start_date = observed.observed_on
            season.start_observed = True
    db.flush()
    recompute_season(db, season)
    db.commit()
    db.refresh(season)
    return _season_out(season)


def read_season(db: Session, block: Block, year: int) -> SeasonOut:
    season = _find_season(db, block.id, year)
    if season is None or season.farm_id != block.farm_id:
        raise AppError("phenology.season_not_found", 404)
    return _season_out(season)


def add_observation(
    db: Session,
    user: AppUser,
    season: BlockSeason,
    body: ObservationIn,
) -> ObservationOut:
    block = _season_block(db, season)
    stage = _require_stage(db, block, body.stage_def_id, "stage_def_id")
    farm = db.get(Farm, season.farm_id)
    if farm is None:
        raise AppError("phenology.season_not_found", 404)
    if body.observed_on > _farm_today(farm):
        raise AppError("validation_error", 422, {"observed_on": "phenology.observed_in_future"})
    is_start = season.start_stage_def_id == stage.id
    if not is_start and (season.start_date is None or body.observed_on < season.start_date):
        raise AppError("validation_error", 422, {"observed_on": "phenology.before_season_start"})
    row = _observation(db, season.id, stage.id)
    if row is None:
        row = StageObservation(
            farm_id=season.farm_id,
            block_season_id=season.id,
            stage_def_id=stage.id,
            observed_on=body.observed_on,
            share_pct=body.share_pct,
            user_id=user.id,
            created_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.observed_on = body.observed_on
        row.share_pct = body.share_pct
        row.user_id = user.id
    if is_start:
        season.start_date = body.observed_on
        season.start_observed = True
    db.flush()
    publish(
        "stage.observed",
        {
            "db": db,
            "farm_id": season.farm_id,
            "block_season_id": season.id,
            "stage_def_id": stage.id,
        },
    )
    db.commit()
    db.refresh(row)
    return _observation_out(row)


def delete_observation(db: Session, season: BlockSeason, obs_id: uuid.UUID) -> None:
    row = db.get(StageObservation, obs_id)
    if row is None or row.block_season_id != season.id or row.farm_id != season.farm_id:
        raise AppError("phenology.observation_not_found", 404)
    stage_id = row.stage_def_id
    db.delete(row)
    if season.start_stage_def_id == stage_id:
        season.start_date = None
        season.start_observed = False
    db.flush()
    publish(
        "stage.observed",
        {
            "db": db,
            "farm_id": season.farm_id,
            "block_season_id": season.id,
            "stage_def_id": stage_id,
        },
    )
    db.commit()


def read_block_stages(db: Session, block: Block, year: int) -> BlockStagesOut:
    season = _find_season(db, block.id, year)
    if season is None or season.farm_id != block.farm_id:
        raise AppError("phenology.season_not_found", 404)
    view = recompute_season(db, season)
    db.commit()
    return _stages_out(view)


def read_farm_summary(db: Session, farm: Farm, crop_id: uuid.UUID) -> StageSummaryOut:
    if db.get(Crop, crop_id) is None:
        raise AppError("catalog.crop_not_found", 404)
    year = _farm_today(farm).year
    blocks = list(
        db.scalars(
            select(Block)
            .where(Block.farm_id == farm.id, Block.crop_id == crop_id)
            .order_by(Block.name, Block.id)
        ).all()
    )
    items: list[SummaryBlockOut] = []
    for block in blocks:
        season = _find_season(db, block.id, year)
        if season is None:
            items.append(
                SummaryBlockOut(
                    block_id=block.id,
                    name=block.name,
                    season_id=None,
                    year=year,
                    current_stage=None,
                    next_stage=None,
                )
            )
            continue
        view = recompute_season(db, season)
        current, nxt = _progress(view.stages, view.today)
        items.append(
            SummaryBlockOut(
                block_id=block.id,
                name=block.name,
                season_id=view.season_id,
                year=year,
                current_stage=None if current is None else _brief(current),
                next_stage=None
                if nxt is None or nxt.on is None
                else SummaryNextOut(stage=_brief(nxt), date=nxt.on),
            )
        )
    db.commit()
    return StageSummaryOut(crop_id=crop_id, blocks=items)


def owned_season(db: Session, user: AppUser, season_id: uuid.UUID) -> BlockSeason:
    season = db.get(BlockSeason, season_id)
    if season is None:
        raise AppError("phenology.season_not_found", 404)
    farm = db.get(Farm, season.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("phenology.season_not_found", 404)
    return season


def recompute_season(db: Session, season: BlockSeason) -> _View:
    """Rewrite this season's predictions. Does not commit."""
    season_id = season.id
    farm = db.get(Farm, season.farm_id)
    if farm is None:
        raise AppError("phenology.season_not_found", 404)
    history_status = _as_history(ensure_history(db, farm))
    current = db.get(BlockSeason, season_id)
    if current is None:
        raise AppError("phenology.season_not_found", 404)
    return _recompute_loaded(db, current, history_status)


def recompute_crop(db: Session, farm_id: uuid.UUID, crop_id: uuid.UUID) -> None:
    """Recompute open and closed seasons of one crop. Does not commit."""
    ids = list(
        db.scalars(
            select(BlockSeason.id)
            .join(Block, Block.id == BlockSeason.block_id)
            .where(BlockSeason.farm_id == farm_id, Block.crop_id == crop_id)
        ).all()
    )
    for season_id in ids:
        season = db.get(BlockSeason, season_id)
        if season is not None:
            recompute_season(db, season)


def recompute_block_seasons(db: Session, block_id: uuid.UUID) -> None:
    """Recompute every season of one block. Does not commit."""
    ids = list(db.scalars(select(BlockSeason.id).where(BlockSeason.block_id == block_id)).all())
    for season_id in ids:
        season = db.get(BlockSeason, season_id)
        if season is not None:
            recompute_season(db, season)


def recompute_farm(db: Session, farm_id: uuid.UUID) -> None:
    """Recompute every season on a farm. Does not commit."""
    ids = list(db.scalars(select(BlockSeason.id).where(BlockSeason.farm_id == farm_id)).all())
    if not ids:
        return
    farm = db.get(Farm, farm_id)
    history_status = _as_history(ensure_history(db, farm)) if farm is not None else "empty"
    for season_id in ids:
        season = db.get(BlockSeason, season_id)
        if season is not None:
            _recompute_loaded(db, season, history_status)


def _recompute_loaded(db: Session, season: BlockSeason, history_status: _History) -> _View:
    farm = db.get(Farm, season.farm_id)
    block = db.get(Block, season.block_id)
    if farm is None or block is None:
        raise AppError("phenology.season_not_found", 404)
    today = _farm_today(farm)
    stages = _stage_rows(db, block.crop_id)
    setting = effective_gdd_setting(db, block)
    targets = _targets(db, season.farm_id, block.crop_id, stages, setting)
    stage_ids = {stage.id for stage in stages}
    observed_rows = [
        row
        for row in db.scalars(
            select(StageObservation).where(StageObservation.block_season_id == season.id)
        ).all()
        if row.stage_def_id in stage_ids
    ]
    observations = {row.stage_def_id: row.observed_on for row in observed_rows}
    start = season.start_date
    series: list[SeriesPoint] = []
    year_maps: list[dict[date, Decimal]] = []
    if start is not None and setting is not None:
        series, samples = _series(db, farm, setting, start, today, history_status)
        year_maps = _past_maps(db, farm, samples, start, history_status)
    views = _stage_views(
        stages,
        targets,
        observations,
        series,
        year_maps,
        start,
        today,
        setting,
        history_status,
    )
    _store(
        db,
        season,
        block,
        views,
        series,
        targets,
        observations,
        setting,
        start,
        today,
        history_status,
    )
    return _View(
        season_id=season.id,
        block_id=season.block_id,
        farm_id=season.farm_id,
        year=season.year,
        start_date=season.start_date,
        start_stage_def_id=season.start_stage_def_id,
        start_observed=season.start_observed,
        status=season.status,
        setting=setting,
        history_status=history_status,
        today=today,
        today_dd=None if start is None or setting is None else calc.counted_through(series, today),
        years_count=len(history_years(db, farm)),
        observations=observed_rows,
        stages=views,
    )


def _stage_views(
    stages: Sequence[StageDef],
    targets: dict[uuid.UUID, _Target],
    observations: dict[uuid.UUID, date],
    series: Sequence[SeriesPoint],
    year_maps: Sequence[dict[date, Decimal]],
    start: date | None,
    today: date,
    setting: EffectiveGddSetting | None,
    history_status: _History,
) -> list[_StageView]:
    if not stages:
        return []
    if start is None or setting is None:
        return [
            _blocked_view(stage, targets[stage.id], observations.get(stage.id), setting, start)
            for stage in stages
        ]
    specs = [(stage.id, stage.sort, targets[stage.id].dd) for stage in stages]
    calls = {
        row.stage_id: row for row in calc.predict(start, series, specs, observations, today=today)
    }
    windows = {
        row.stage_id: row
        for row in calc.predict_range(
            start,
            series,
            specs,
            observations,
            year_maps,
            today=today,
        )
    }
    views: list[_StageView] = []
    for stage in stages:
        call = calls[stage.id]
        target = targets[stage.id]
        window = windows[stage.id]
        earliest = window.earliest if call.label == "predicted" else None
        latest = window.latest if call.label == "predicted" else None
        reason = None if call.label == "observed" else target.reason
        if history_status == "loading" and call.label == "beyond_data":
            reason = None
        views.append(
            _view_from(
                stage,
                PredictionLabel(call.label),
                call.date,
                earliest,
                latest,
                call.dd_needed,
                call.dd_counted,
                target.source if target.dd is not None else None,
                target.citation if target.dd is not None else None,
                reason,
            )
        )
    return views


def _blocked_view(
    stage: StageDef,
    target: _Target,
    observed_on: date | None,
    setting: EffectiveGddSetting | None,
    start: date | None,
) -> _StageView:
    if observed_on is not None:
        return _view_from(
            stage,
            PredictionLabel.observed,
            observed_on,
            None,
            None,
            target.dd,
            None,
            target.source if target.dd is not None else None,
            target.citation if target.dd is not None else None,
            None,
        )
    reason = target.reason
    if setting is None:
        reason = _NO_SETTING
    elif reason is None and start is None:
        reason = _NO_START
    return _view_from(
        stage,
        PredictionLabel.not_enough_data,
        None,
        None,
        None,
        target.dd,
        None,
        target.source if target.dd is not None else None,
        target.citation if target.dd is not None else None,
        reason,
    )


def _view_from(
    stage: StageDef,
    label: PredictionLabel,
    on: date | None,
    earliest: date | None,
    latest: date | None,
    dd_needed: Decimal | None,
    dd_counted: Decimal | None,
    dd_source: DdSource | None,
    citation: str | None,
    reason: str | None,
) -> _StageView:
    return _StageView(
        stage_id=stage.id,
        code=stage.code,
        sort=stage.sort,
        name_fr=stage.name_fr,
        name_ar=stage.name_ar,
        name_en=stage.name_en,
        label=label,
        on=on,
        earliest=earliest,
        latest=latest,
        dd_needed=dd_needed,
        dd_counted=dd_counted,
        dd_source=dd_source,
        citation=citation,
        reason=reason,
    )


def _store(
    db: Session,
    season: BlockSeason,
    block: Block,
    views: Sequence[_StageView],
    series: Sequence[SeriesPoint],
    targets: dict[uuid.UUID, _Target],
    observations: dict[uuid.UUID, date],
    setting: EffectiveGddSetting | None,
    start: date | None,
    today: date,
    history_status: str,
) -> None:
    existing = list(
        db.scalars(
            select(StagePrediction).where(StagePrediction.block_season_id == season.id)
        ).all()
    )
    previous = {row.stage_def_id: row.predicted_on for row in existing}
    for row in existing:
        db.delete(row)
    db.flush()
    for row in existing:
        db.expunge(row)
    digest = _inputs_hash(
        {
            "start": None if start is None else start.isoformat(),
            "today": today.isoformat(),
            "history_status": history_status,
            "base_c": None if setting is None else _canon(setting.base_c),
            "upper_c": None if setting is None else _canon(setting.upper_c),
            "method": None if setting is None else setting.method.value,
            "stages": [
                {
                    "id": str(stage_id),
                    "dd": _canon(target.dd),
                    "reason": target.reason,
                }
                for stage_id, target in sorted(targets.items(), key=lambda item: str(item[0]))
            ],
            "observations": [
                {"stage": str(stage_id), "on": observed.isoformat()}
                for stage_id, observed in sorted(
                    observations.items(), key=lambda item: str(item[0])
                )
            ],
            "series": [
                {"date": day.isoformat(), "gdd": _canon(gdd), "kind": kind}
                for day, gdd, kind in series
            ],
        }
    )
    run_at = datetime.now(UTC)
    moved: list[tuple[uuid.UUID, date | None, date | None]] = []
    for view in views:
        db.add(
            StagePrediction(
                block_season_id=season.id,
                stage_def_id=view.stage_id,
                farm_id=season.farm_id,
                label=view.label,
                predicted_on=view.on,
                earliest=view.earliest,
                latest=view.latest,
                dd_needed=view.dd_needed,
                dd_counted=view.dd_counted,
                reason=view.reason,
                run_at=run_at,
                inputs_hash=digest,
            )
        )
        old = previous.get(view.stage_id)
        had_row = view.stage_id in previous
        if (had_row or view.on is not None) and old != view.on:
            moved.append((view.stage_id, old, view.on))
    db.flush()
    for stage_id, old, new in moved:
        publish(
            "stage.predicted",
            {
                "db": db,
                "farm_id": season.farm_id,
                "block_id": block.id,
                "block_season_id": season.id,
                "stage_def_id": stage_id,
                "date": new,
                "previous_date": old,
            },
        )


def _series(
    db: Session,
    farm: Farm,
    setting: EffectiveGddSetting,
    start: date,
    today: date,
    history_status: _History,
) -> tuple[list[SeriesPoint], list[tuple[date, Decimal]]]:
    """Observed weather through yesterday, then forecast, then calendar-day GDD."""
    end = start + timedelta(days=_HORIZON_DAYS)
    weather = db.scalars(
        select(WeatherDaily).where(
            WeatherDaily.farm_id == farm.id,
            WeatherDaily.date >= start,
            WeatherDaily.date <= end,
        )
    ).all()
    by_day = {row.date: row for row in weather}
    samples: list[tuple[date, Decimal]] = []
    means: dict[tuple[int, int], Decimal] = {}
    if history_status == "ready":
        samples = _history_gdd(db, farm.id, setting)
        means = _calendar_means(samples)
    points: list[SeriesPoint] = []
    day = start
    while day <= end:
        row = by_day.get(day)
        gdd = None if row is None else _temps_gdd(row.tmin_c, row.tmax_c, setting)
        if row is not None and gdd is not None and day < today and not row.is_forecast:
            points.append((day, gdd, "observed_weather"))
        elif row is not None and gdd is not None and (row.is_forecast or day >= today):
            points.append((day, gdd, "forecast"))
        elif history_status == "ready":
            average = means.get((day.month, day.day))
            if average is not None:
                points.append((day, average, "average"))
        day += timedelta(days=1)
    return points, samples


def _history_gdd(
    db: Session, farm_id: uuid.UUID, setting: EffectiveGddSetting
) -> list[tuple[date, Decimal]]:
    rows = db.scalars(select(HistoryDaily).where(HistoryDaily.farm_id == farm_id)).all()
    samples: list[tuple[date, Decimal]] = []
    for row in rows:
        gdd = _temps_gdd(row.tmin_c, row.tmax_c, setting)
        if gdd is not None:
            samples.append((row.date, gdd))
    return samples


def _calendar_means(samples: Sequence[tuple[date, Decimal]]) -> dict[tuple[int, int], Decimal]:
    """Mean of per-day GDD. ``tmin_c`` carries GDD so the 29 February rule is reused."""
    temps = [CalendarDayTemps(day=day, tmin_c=gdd, tmax_c=None) for day, gdd in samples]
    cache: dict[tuple[int, int], Decimal | None] = {}

    def mean(month: int, day: int) -> Decimal | None:
        key = (month, day)
        if key not in cache:
            cache[key] = average_by_calendar_day(temps, month, day).tmin_c
        return cache[key]

    found: dict[tuple[int, int], Decimal] = {}
    for month in range(1, 13):
        for day in range(1, 32):
            try:
                date(2024 if month == 2 and day == 29 else 2023, month, day)
            except ValueError:
                continue
            value = mean(month, day)
            if value is not None:
                found[(month, day)] = value
    return found


def _past_maps(
    db: Session,
    farm: Farm,
    samples: Sequence[tuple[date, Decimal]],
    start: date,
    history_status: _History,
) -> list[dict[date, Decimal]]:
    if history_status != "ready":
        return []
    years = [year for year in history_years(db, farm) if year < start.year]
    grouped: dict[int, dict[date, Decimal]] = {year: {} for year in years}
    for day, gdd in samples:
        bucket = grouped.get(day.year)
        if bucket is not None:
            bucket[day] = gdd
    return [grouped[year] for year in years]


def _targets(
    db: Session,
    farm_id: uuid.UUID,
    crop_id: uuid.UUID | None,
    stages: Sequence[StageDef],
    setting: EffectiveGddSetting | None,
) -> dict[uuid.UUID, _Target]:
    if crop_id is None or not stages:
        return {}
    if setting is None:
        return {stage.id: _Target(None, None, None, _NO_SETTING) for stage in stages}
    farm_rows = {
        row.stage_def_id: row
        for row in db.scalars(
            select(StageDd).where(StageDd.farm_id == farm_id, StageDd.crop_id == crop_id)
        ).all()
    }
    global_rows = {
        row.stage_def_id: row
        for row in db.scalars(
            select(StageDd).where(
                StageDd.farm_id.is_(None),
                StageDd.variety_id.is_(None),
                StageDd.crop_id == crop_id,
            )
        ).all()
    }
    chosen: dict[uuid.UUID, _Target] = {}
    for stage in stages:
        row = farm_rows.get(stage.id)
        if row is None:
            row = global_rows.get(stage.id)
        chosen[stage.id] = _target_from(row, setting)
    return chosen


def _upper_matches(left: Decimal | None, right: Decimal | None) -> bool:
    """Both thresholds absent, or the same temperature."""
    if left is None or right is None:
        return left is None and right is None
    return left == right


def _target_from(row: StageDd | None, setting: EffectiveGddSetting) -> _Target:
    if row is None:
        return _Target(None, None, None, None)
    if (
        row.base_c != setting.base_c
        or not _upper_matches(row.upper_c, setting.upper_c)
        or row.method != setting.method
    ):
        return _Target(None, None, None, _MISMATCH)
    if row.farm_id is not None:
        return _Target(row.dd_value, "entered", None, None)
    return _Target(row.dd_value, "literature", row.citation, None)


def _temps_gdd(
    tmin_c: Decimal | None,
    tmax_c: Decimal | None,
    setting: EffectiveGddSetting,
) -> Decimal | None:
    if tmin_c is None or tmax_c is None:
        return None
    if setting.method == GddMethod.single_sine:
        return gdd_single_sine(tmax_c, tmin_c, setting.base_c, setting.upper_c)
    return gdd_average(tmax_c, tmin_c, setting.base_c, setting.upper_c)


def _stage_rows(db: Session, crop_id: uuid.UUID | None) -> list[StageDef]:
    if crop_id is None:
        return []
    return list(
        db.scalars(
            select(StageDef)
            .where(StageDef.crop_id == crop_id)
            .order_by(StageDef.sort, StageDef.code)
        ).all()
    )


def _find_season(db: Session, block_id: uuid.UUID, year: int) -> BlockSeason | None:
    return db.scalar(
        select(BlockSeason).where(BlockSeason.block_id == block_id, BlockSeason.year == year)
    )


def _observation(
    db: Session,
    season_id: uuid.UUID,
    stage_id: uuid.UUID | None,
) -> StageObservation | None:
    if stage_id is None:
        return None
    return db.scalar(
        select(StageObservation).where(
            StageObservation.block_season_id == season_id,
            StageObservation.stage_def_id == stage_id,
        )
    )


def _season_block(db: Session, season: BlockSeason) -> Block:
    block = db.get(Block, season.block_id)
    if block is None or block.farm_id != season.farm_id:
        raise AppError("phenology.season_not_found", 404)
    return block


def _require_stage(db: Session, block: Block, stage_id: uuid.UUID, field: str) -> StageDef:
    stage = db.get(StageDef, stage_id)
    if block.crop_id is None or stage is None or stage.crop_id != block.crop_id:
        raise AppError("validation_error", 422, {field: "phenology.stage_not_found"})
    return stage


def _farm_today(farm: Farm) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date()


def _as_history(status: str) -> _History:
    if status == "ready" or status == "loading" or status == "empty":
        return status
    return "empty"


def _progress(
    stages: Sequence[_StageView], today: date
) -> tuple[_StageView | None, _StageView | None]:
    passed = [
        stage
        for stage in stages
        if stage.label == PredictionLabel.observed
        or (stage.label == PredictionLabel.predicted and stage.on is not None and stage.on <= today)
    ]
    current = passed[-1] if passed else None
    start = 0
    if current is not None:
        start = (
            next(index for index, stage in enumerate(stages) if stage.stage_id == current.stage_id)
            + 1
        )
    nxt = next(
        (
            stage
            for stage in stages[start:]
            if stage.label == PredictionLabel.predicted and stage.on is not None
        ),
        None,
    )
    return current, nxt


def _brief(stage: _StageView) -> StageBrief:
    return StageBrief(
        id=stage.stage_id,
        code=stage.code,
        name={"fr": stage.name_fr, "ar": stage.name_ar, "en": stage.name_en},
    )


def _season_out(season: BlockSeason) -> SeasonOut:
    return SeasonOut(
        id=season.id,
        block_id=season.block_id,
        year=season.year,
        start_date=season.start_date,
        start_stage_def_id=season.start_stage_def_id,
        start_observed=season.start_observed,
        status=season.status,
    )


def _observation_out(row: StageObservation) -> ObservationOut:
    return ObservationOut(
        id=row.id,
        block_season_id=row.block_season_id,
        stage_def_id=row.stage_def_id,
        observed_on=row.observed_on,
        share_pct=row.share_pct,
    )


def _stages_out(view: _View) -> BlockStagesOut:
    current, nxt = _progress(view.stages, view.today)
    setting = None
    if view.setting is not None:
        setting = SettingOut(
            base_c=view.setting.base_c,
            upper_c=view.setting.upper_c,
            method=view.setting.method,
        )
    start_stage = None
    if view.start_stage_def_id is not None:
        found = next(
            (stage for stage in view.stages if stage.stage_id == view.start_stage_def_id),
            None,
        )
        if found is not None:
            start_stage = _brief(found)
    order = {stage.stage_id: stage.sort for stage in view.stages}
    observed = sorted(
        view.observations,
        key=lambda row: (order.get(row.stage_def_id, 0), row.observed_on, str(row.id)),
    )
    return BlockStagesOut(
        season=SeasonOut(
            id=view.season_id,
            block_id=view.block_id,
            year=view.year,
            start_date=view.start_date,
            start_stage_def_id=view.start_stage_def_id,
            start_stage=start_stage,
            start_observed=view.start_observed,
            status=view.status,
        ),
        setting=setting,
        history_status=view.history_status,
        history=HistoryOut(years_count=view.years_count, status=view.history_status),
        today=TodayOut(
            dd_counted=view.today_dd,
            current_stage=None if current is None else _brief(current),
            next_stage=None if nxt is None else _brief(nxt),
        ),
        stages=[_row_out(stage) for stage in view.stages],
        observations=[
            ObservationItemOut(
                id=row.id,
                stage_def_id=row.stage_def_id,
                observed_on=row.observed_on,
                share_pct=row.share_pct,
            )
            for row in observed
        ],
    )


def _row_out(stage: _StageView) -> StageRowOut:
    return StageRowOut(
        stage=_brief(stage),
        label=stage.label,
        date=stage.on,
        earliest=stage.earliest,
        latest=stage.latest,
        dd_needed=stage.dd_needed,
        dd_counted=stage.dd_counted,
        dd_source=stage.dd_source,
        citation=stage.citation,
        reason=stage.reason,
    )


def _canon(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return _canon(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _inputs_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _on_stage_observed(payload: dict[str, Any]) -> None:
    db = payload.get("db")
    season_id = payload.get("block_season_id")
    if not isinstance(db, Session) or not isinstance(season_id, uuid.UUID):
        return
    season = db.get(BlockSeason, season_id)
    if season is None:
        return
    recompute_season(db, season)


def _on_weather_daily_ready(payload: dict[str, Any]) -> None:
    db = payload.get("db")
    farm_id = payload.get("farm_id")
    if not isinstance(db, Session) or not isinstance(farm_id, uuid.UUID):
        return
    recompute_farm(db, farm_id)


_registered = False


def register_handlers() -> None:
    global _registered
    if _registered:
        return
    subscribe("stage.observed", _on_stage_observed)
    subscribe("weather.daily_ready", _on_weather_daily_ready)
    _registered = True


register_handlers()
