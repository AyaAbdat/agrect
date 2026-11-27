"""Background job bodies. Each runs per farm, in its own session, and is idempotent.

One farm's failure is logged and written to ``job_run`` with status ``error``; the
other farms still run. Daily jobs are keyed by farm + farm-local date: they run
once the farm-local time has passed their hour and no ``ok`` run exists for that
farm today, so a missed slot (server down) is caught up at the next tick. A daily
job that failed for a farm is retried at most 3 times that farm-local day, at least
1 h after the previous attempt; then it waits for the next day. The hourly refresh
is never retried: the next hour is the retry.
"""

from __future__ import annotations

import logging
import time as monotonic
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.jobs.models import JobRun, JobStatus
from app.modules.equipment.service import farm_maintenance_due
from app.modules.farms.models import Farm
from app.modules.farms.service import read_lat_lon
from app.modules.weather import service as weather

logger = logging.getLogger(__name__)

SERVICE_REFRESH = "service_refresh"
DERIVE_DAILY = "derive_daily"
HISTORY_BACKFILL = "history_backfill"
MAINTENANCE_DUE = "maintenance_due"
JOB_NAMES = (SERVICE_REFRESH, DERIVE_DAILY, HISTORY_BACKFILL, MAINTENANCE_DUE)

# Farm-local time after which each daily job runs (system design: jobs and schedules).
DAILY_AT = {
    DERIVE_DAILY: time(0, 30),
    HISTORY_BACKFILL: time(3, 0),
    MAINTENANCE_DUE: time(6, 0),
}
RETENTION = timedelta(days=30)
MAX_DAILY_RETRIES = 3
RETRY_AFTER = timedelta(hours=1)
_MESSAGE_MAX = 500
_SKIPPED_NO_LOCATION = "skipped.location_required"

SessionFactory = Callable[[], Session]
FarmTask = Callable[[Session, Farm, datetime], str | None]


def _now(now: datetime | None) -> datetime:
    return datetime.now(UTC) if now is None else now.astimezone(UTC)


def _local(farm: Farm, now: datetime) -> datetime:
    return now.astimezone(ZoneInfo(farm.timezone))


def _farm_ids(factory: SessionFactory) -> list[uuid.UUID]:
    with factory() as db:
        return list(db.scalars(select(Farm.id).order_by(Farm.id)).all())


def _record(
    db: Session,
    job: str,
    farm_id: uuid.UUID | None,
    started_at: datetime,
    elapsed_s: float,
    status: JobStatus,
    message: str | None,
) -> None:
    db.add(
        JobRun(
            job=job,
            farm_id=farm_id,
            started_at=started_at,
            finished_at=started_at + timedelta(seconds=elapsed_s),
            status=status,
            message=None if message is None else message[:_MESSAGE_MAX],
        )
    )
    db.commit()


def _daily_due(db: Session, job: str, farm: Farm, local_now: datetime) -> bool:
    """Whether a daily job should run for this farm now (farm-local day + retry cap)."""
    if local_now.time() < DAILY_AT[job]:
        return False
    midnight = datetime.combine(local_now.date(), time(0), tzinfo=local_now.tzinfo)
    today = db.execute(
        select(JobRun.status, JobRun.started_at).where(
            JobRun.job == job,
            JobRun.farm_id == farm.id,
            JobRun.started_at >= midnight.astimezone(UTC),
            JobRun.started_at < (midnight + timedelta(days=1)).astimezone(UTC),
        )
    ).all()
    if any(status == JobStatus.ok for status, _started in today):
        return False
    failures = [started for status, started in today if status == JobStatus.error]
    if not failures:
        return True
    if len(failures) > MAX_DAILY_RETRIES:
        return False
    return local_now - max(failures) >= RETRY_AFTER


def _run_for_farm(
    factory: SessionFactory,
    job: str,
    farm_id: uuid.UUID,
    clock: Callable[[], datetime],
    task: FarmTask,
    *,
    daily: bool,
) -> JobStatus | None:
    """Run ``task`` for one farm; returns the recorded status, or None when skipped."""
    db = factory()
    started_at = clock()
    try:
        farm = db.get(Farm, farm_id)
        if farm is None:
            return None
        if daily and not _daily_due(db, job, farm, _local(farm, started_at)):
            return None
        began = monotonic.perf_counter()
        try:
            message = task(db, farm, started_at)
            db.commit()
        except Exception as exc:
            logger.exception("job %s failed for farm %s", job, farm_id)
            db.rollback()
            elapsed = monotonic.perf_counter() - began
            error = f"{type(exc).__name__}: {exc}"
            _record(db, job, farm_id, started_at, elapsed, JobStatus.error, error)
            return JobStatus.error
        elapsed = monotonic.perf_counter() - began
        _record(db, job, farm_id, started_at, elapsed, JobStatus.ok, message)
        return JobStatus.ok
    finally:
        db.close()


def _for_each_farm(
    job: str,
    task: FarmTask,
    *,
    daily: bool,
    factory: SessionFactory,
    now: datetime | None,
) -> dict[uuid.UUID, JobStatus]:
    # One clock for started_at and the daily/retry checks: the given moment (tests,
    # catch-up) or the real time at each farm's start.
    fixed = None if now is None else _now(now)

    def clock() -> datetime:
        return fixed if fixed is not None else datetime.now(UTC)

    results: dict[uuid.UUID, JobStatus] = {}
    for farm_id in _farm_ids(factory):
        status = _run_for_farm(factory, job, farm_id, clock, task, daily=daily)
        if status is not None:
            results[farm_id] = status
    return results


def _has_location(db: Session, farm: Farm) -> bool:
    latitude, longitude = read_lat_lon(db, farm)
    return latitude is not None and longitude is not None


# --- tasks ------------------------------------------------------------------


def _refresh_task(db: Session, farm: Farm, _now: datetime) -> str:
    if not _has_location(db, farm):
        return _SKIPPED_NO_LOCATION
    out = weather.refresh(db, farm)
    return f"hours={out.hours} days={out.days}"


def _derive_task(db: Session, farm: Farm, now: datetime) -> str:
    yesterday: date = _local(farm, now).date() - timedelta(days=1)
    days = weather.rederive_day(db, farm, yesterday)
    return f"date={yesterday.isoformat()} days={days}"


def _history_task(db: Session, farm: Farm, _now: datetime) -> str:
    if not _has_location(db, farm):
        return _SKIPPED_NO_LOCATION
    status = weather.history_backfill(db, farm)
    return f"days={status.days} status={status.status}"


def _maintenance_task(db: Session, farm: Farm, _now: datetime) -> str:
    items = farm_maintenance_due(db, farm).items
    overdue = sum(1 for item in items if item.due.overdue)
    logger.info("maintenance due for farm %s: %d due, %d overdue", farm.id, len(items), overdue)
    return f"due={len(items)} overdue={overdue}"


# --- job entry points -------------------------------------------------------


def service_refresh(
    factory: SessionFactory = SessionLocal, now: datetime | None = None
) -> dict[uuid.UUID, JobStatus]:
    """Hourly: Open-Meteo refresh per farm (upserts hours and re-derives touched days)."""
    return _for_each_farm(SERVICE_REFRESH, _refresh_task, daily=False, factory=factory, now=now)


def derive_daily(
    factory: SessionFactory = SessionLocal, now: datetime | None = None
) -> dict[uuid.UUID, JobStatus]:
    """After 00:30 farm-local: re-derive yesterday and publish weather.daily_ready."""
    return _for_each_farm(DERIVE_DAILY, _derive_task, daily=True, factory=factory, now=now)


def history_backfill(
    factory: SessionFactory = SessionLocal, now: datetime | None = None
) -> dict[uuid.UUID, JobStatus]:
    """After 03:00 farm-local: fetch only the missing archive ranges."""
    return _for_each_farm(HISTORY_BACKFILL, _history_task, daily=True, factory=factory, now=now)


def maintenance_due(
    factory: SessionFactory = SessionLocal, now: datetime | None = None
) -> dict[uuid.UUID, JobStatus]:
    """After 06:00 farm-local: count due and overdue maintenance; nothing is stored but the run."""
    return _for_each_farm(MAINTENANCE_DUE, _maintenance_task, daily=True, factory=factory, now=now)


def prune_job_runs(factory: SessionFactory = SessionLocal, now: datetime | None = None) -> int:
    """Delete job_run rows older than 30 days."""
    cutoff = _now(now) - RETENTION
    with factory() as db:
        result = db.execute(delete(JobRun).where(JobRun.started_at < cutoff))
        db.commit()
        return int(getattr(result, "rowcount", 0) or 0)


def daily_tick(factory: SessionFactory = SessionLocal, now: datetime | None = None) -> None:
    """Every 15 minutes: run each daily job that is due for a farm, then prune old runs."""
    for job in (derive_daily, history_backfill, maintenance_due):
        try:
            job(factory, now)
        except Exception:
            logger.exception("daily job %s failed", job.__name__)
    try:
        prune_job_runs(factory, now)
    except Exception:
        logger.exception("job_run prune failed")
