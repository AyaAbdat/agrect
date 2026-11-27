"""Background jobs: start flag, advisory lock, idempotent job bodies, job_run, status API."""

import time as monotonic
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import engine
from app.jobs import runner
from app.jobs.models import JobRun, JobStatus
from app.jobs.scheduler import (
    JobsSupervisor,
    start_jobs_if_enabled,
    start_scheduler,
    stop_scheduler,
)
from app.main import app
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from app.modules.weather.client import ArchiveDay, HourlyObservation, WeatherProviderError
from app.modules.weather.models import HistoryDaily, WeatherDaily, WeatherHourly

ZONE = ZoneInfo("Africa/Algiers")


def _local_now(hour: int, minute: int = 0) -> datetime:
    today = datetime.now(ZONE).date()
    return datetime.combine(today, time(hour, minute), tzinfo=ZONE)


def _hours_for(day: date) -> list[HourlyObservation]:
    rows = []
    for hour in range(24):
        ts = datetime.combine(day, time(hour), tzinfo=ZONE).astimezone(UTC)
        rows.append(
            HourlyObservation(
                ts=ts,
                temp_c=Decimal(10 + hour % 12),
                rh_pct=Decimal("50"),
                rain_mm=Decimal("0"),
                rain_prob_pct=None,
                wind_ms=Decimal("1.5"),
                gust_ms=Decimal("3"),
                wind_dir_deg=Decimal("180"),
                rad_wm2=Decimal("100"),
                et0_mm=Decimal("0.2"),
            )
        )
    return rows


class _Feed:
    """Mocked Open-Meteo forecast; fails for one latitude to test isolation."""

    def __init__(self, rows: list[HourlyObservation], fail_lat: Decimal | None = None) -> None:
        self.rows = rows
        self.fail_lat = fail_lat
        self.calls = 0

    def __call__(self, latitude: Decimal, _longitude: Decimal) -> list[HourlyObservation]:
        self.calls += 1
        if self.fail_lat is not None and Decimal(str(latitude)) == self.fail_lat:
            raise WeatherProviderError("down")
        return self.rows


def _farm(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    email: str,
    lat: str = "36.5",
) -> Farm:
    user = make_user(email, "password-jobs")
    return make_farm(user, "Jobs farm", Decimal(lat), Decimal("3.2"))


def _runs(db: Session, job: str, farm: Farm) -> list[JobRun]:
    db.expire_all()
    return list(
        db.scalars(
            select(JobRun)
            .where(JobRun.job == job, JobRun.farm_id == farm.id)
            .order_by(JobRun.started_at)
        ).all()
    )


def test_scheduler_not_started_when_disabled() -> None:
    disabled = get_settings().model_copy(update={"jobs_enabled": False})
    assert start_jobs_if_enabled(disabled) is None
    assert get_settings().jobs_enabled is False
    with TestClient(app):
        assert app.state.scheduler is None


def _backend_pid(supervisor: JobsSupervisor) -> int:
    connection = supervisor._connection
    assert connection is not None
    pid = connection.scalar(text("SELECT pg_backend_pid()"))
    connection.commit()
    return int(pid)


def _terminate(pid: int) -> None:
    """Simulate a dropped lock connection: the server ends that session."""
    with engine.connect() as admin:
        assert admin.scalar(text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}) is True
        admin.commit()
    # The server releases the session lock as the backend exits; wait until it has.
    with engine.connect() as admin:
        for _ in range(50):
            alive = admin.scalar(
                text("SELECT count(*) FROM pg_stat_activity WHERE pid = :pid"), {"pid": pid}
            )
            admin.commit()
            if alive == 0:
                return
            monotonic.sleep(0.1)
    raise AssertionError("backend did not exit")


def _holders(*supervisors: JobsSupervisor) -> int:
    return sum(1 for supervisor in supervisors if supervisor.holds_lock)


def test_advisory_lock_allows_one_scheduler() -> None:
    enabled = get_settings().model_copy(update={"jobs_enabled": True})
    first = start_jobs_if_enabled(enabled, paused=True)
    assert first is not None
    second = start_scheduler(paused=True)
    try:
        assert first.scheduler.running
        assert {job.id for job in first.scheduler.get_jobs()} == {
            "service_refresh",
            "daily_tick",
            "jobs_lock",
        }
        assert first.holds_lock
        assert not first.work_jobs_paused()
        # A second worker cannot take the lock: it stands by with its work jobs paused.
        assert not second.holds_lock
        assert second.work_jobs_paused()
        assert second.ensure_lock() is False
        assert _holders(first, second) == 1
    finally:
        stop_scheduler(first)
    # The holder stopped and released the lock: the standby takes it on its next try.
    try:
        assert second.ensure_lock() is True
        assert not second.work_jobs_paused()
    finally:
        stop_scheduler(second)


def test_lost_lock_connection_is_recovered() -> None:
    holder = start_scheduler(paused=True)
    try:
        assert holder.holds_lock
        _terminate(_backend_pid(holder))
        # Next tick: SELECT 1 fails, a new connection takes the free lock, jobs resume.
        assert holder.ensure_lock() is True
        assert holder.holds_lock
        assert not holder.work_jobs_paused()
        assert holder.ensure_lock() is True
    finally:
        stop_scheduler(holder)


def test_standby_takes_over_and_old_holder_pauses() -> None:
    holder = start_scheduler(paused=True)
    standby = start_scheduler(paused=True)
    try:
        assert _holders(holder, standby) == 1
        _terminate(_backend_pid(holder))
        # The standby's 5-minute retry takes the lock the dead session released.
        assert standby.ensure_lock() is True
        # The old holder notices its lost connection, cannot retake the lock, and pauses.
        assert holder.ensure_lock() is False
        assert not holder.holds_lock
        assert holder.work_jobs_paused()
        assert not standby.work_jobs_paused()
        assert _holders(holder, standby) == 1
    finally:
        stop_scheduler(standby)
        stop_scheduler(holder)


def test_guarded_work_skips_without_the_lock() -> None:
    holder = start_scheduler(paused=True)
    standby = start_scheduler(paused=True)
    ran: list[str] = []
    try:
        standby._guarded(lambda: ran.append("standby"))()
        holder._guarded(lambda: ran.append("holder"))()
        assert ran == ["holder"]
    finally:
        stop_scheduler(standby)
        stop_scheduler(holder)


def test_daily_retry_cap(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    farm = _farm(make_user, make_farm, "jobs-retry@agrect.app")

    def broken(*_args: object) -> int:
        raise RuntimeError("derive failed")

    monkeypatch.setattr("app.modules.weather.service.rederive_day", broken)
    error = {farm.id: JobStatus.error}
    assert runner.derive_daily(now=_local_now(0, 45)) == error  # first attempt
    assert runner.derive_daily(now=_local_now(1, 15)) == {}  # under 1 h since the failure
    assert runner.derive_daily(now=_local_now(1, 45)) == error  # retry 1
    assert runner.derive_daily(now=_local_now(2, 50)) == error  # retry 2
    assert runner.derive_daily(now=_local_now(3, 55)) == error  # retry 3
    assert runner.derive_daily(now=_local_now(5, 30)) == {}  # cap reached: wait for tomorrow
    assert runner.derive_daily(now=_local_now(23, 50)) == {}
    runs = _runs(db, runner.DERIVE_DAILY, farm)
    assert [run.status for run in runs] == [JobStatus.error] * 4
    assert runs[0].message == "RuntimeError: derive failed"

    # Next farm-local day: a fresh attempt; a success then stops further runs.
    tomorrow = _local_now(0, 45) + timedelta(days=1)
    assert runner.derive_daily(now=tomorrow) == error
    monkeypatch.setattr("app.modules.weather.service.rederive_day", lambda *_args: 0)
    assert runner.derive_daily(now=tomorrow + timedelta(hours=1)) == {farm.id: JobStatus.ok}
    assert runner.derive_daily(now=tomorrow + timedelta(hours=3)) == {}


def test_hourly_refresh_is_not_retried(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    farm = _farm(make_user, make_farm, "jobs-noretry@agrect.app")
    feed = _Feed([], fail_lat=Decimal("36.5"))
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert runner.service_refresh() == {farm.id: JobStatus.error}
    assert feed.calls == 1
    assert len(_runs(db, runner.SERVICE_REFRESH, farm)) == 1


def test_service_refresh_idempotent_and_isolated(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = _farm(make_user, make_farm, "jobs-good@agrect.app")
    bad = _farm(make_user, make_farm, "jobs-bad@agrect.app", lat="35.1")
    yesterday = datetime.now(ZONE).date() - timedelta(days=1)
    feed = _Feed(_hours_for(yesterday), fail_lat=Decimal("35.1"))
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)

    first = runner.service_refresh()
    assert first[good.id] == JobStatus.ok
    assert first[bad.id] == JobStatus.error
    count = db.scalar(
        select(func.count()).select_from(WeatherHourly).where(WeatherHourly.farm_id == good.id)
    )
    assert count == 24

    second = runner.service_refresh()
    assert second[good.id] == JobStatus.ok
    assert (
        db.scalar(
            select(func.count()).select_from(WeatherHourly).where(WeatherHourly.farm_id == good.id)
        )
        == 24
    )
    good_runs = _runs(db, runner.SERVICE_REFRESH, good)
    assert [run.status for run in good_runs] == [JobStatus.ok, JobStatus.ok]
    assert good_runs[0].message == "hours=24 days=1"
    assert good_runs[0].finished_at is not None
    bad_runs = _runs(db, runner.SERVICE_REFRESH, bad)
    assert [run.status for run in bad_runs] == [JobStatus.error, JobStatus.error]
    assert bad_runs[0].message is not None
    assert bad_runs[0].message.startswith("WeatherProviderError")


def test_derive_daily_once_per_local_day(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    farm = _farm(make_user, make_farm, "jobs-derive@agrect.app")
    yesterday = datetime.now(ZONE).date() - timedelta(days=1)
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", _Feed(_hours_for(yesterday)))
    runner.service_refresh()
    db.execute(
        WeatherDaily.__table__.delete().where(
            WeatherDaily.farm_id == farm.id, WeatherDaily.date == yesterday
        )
    )
    db.commit()
    published: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.modules.weather.service.publish",
        lambda name, payload: published.append({"name": name, **payload}),
    )

    assert runner.derive_daily(now=_local_now(0, 15)) == {}
    assert _runs(db, runner.DERIVE_DAILY, farm) == []

    assert runner.derive_daily(now=_local_now(0, 45)) == {farm.id: JobStatus.ok}
    assert runner.derive_daily(now=_local_now(5, 0)) == {}
    runs = _runs(db, runner.DERIVE_DAILY, farm)
    assert len(runs) == 1
    assert runs[0].message == f"date={yesterday.isoformat()} days=1"
    db.expire_all()
    derived = db.scalar(
        select(WeatherDaily).where(WeatherDaily.farm_id == farm.id, WeatherDaily.date == yesterday)
    )
    assert derived is not None
    assert [(item["name"], item["from_date"]) for item in published] == [
        ("weather.daily_ready", yesterday)
    ]


def test_history_backfill_fetches_only_missing(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    farm = _farm(make_user, make_farm, "jobs-history@agrect.app")
    calls: list[tuple[date, date]] = []

    def fake(_lat: Decimal, _lon: Decimal, start: date, end: date, _tz: str) -> list[ArchiveDay]:
        calls.append((start, end))
        days = []
        cursor = start
        while cursor <= end:
            days.append(ArchiveDay(cursor, Decimal("1"), Decimal("15"), Decimal("0"), Decimal("2")))
            cursor += timedelta(days=1)
        return days

    monkeypatch.setattr("app.modules.weather.service.fetch_archive", fake)
    monkeypatch.setattr(get_settings(), "history_years", 1)

    assert runner.history_backfill(now=_local_now(2, 0)) == {}
    assert calls == []
    assert runner.history_backfill(now=_local_now(3, 5)) == {farm.id: JobStatus.ok}
    fetched = len(calls)
    assert fetched > 0
    stored = db.scalar(
        select(func.count()).select_from(HistoryDaily).where(HistoryDaily.farm_id == farm.id)
    )
    assert stored is not None and stored > 300

    # Same day: keyed by farm + date, so it does not run again.
    assert runner.history_backfill(now=_local_now(4, 0)) == {}
    # Even forced to run again (a new day), nothing is missing, so nothing is fetched.
    db.execute(JobRun.__table__.delete())
    db.commit()
    assert runner.history_backfill(now=_local_now(4, 0)) == {farm.id: JobStatus.ok}
    assert len(calls) == fetched
    assert (
        db.scalar(
            select(func.count()).select_from(HistoryDaily).where(HistoryDaily.farm_id == farm.id)
        )
        == stored
    )


def test_maintenance_due_counts_and_location_skip(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user("jobs-maint@agrect.app", "password-jobs")
    farm = make_farm(user, "Maint farm", Decimal("36.5"), Decimal("3.2"))
    headers = auth_header(user)
    machine = client.post(
        f"/v1/farms/{farm.id}/machines", headers=headers, json={"type": "tractor", "name": "T1"}
    ).json()
    last = (datetime.now(ZONE).date() - timedelta(days=200)).isoformat()
    created = client.post(
        f"/v1/machines/{machine['id']}/maintenance",
        headers=headers,
        json={"task": "Filters", "interval_days": 180, "last_done_date": last},
    )
    assert created.status_code == 201, created.text

    assert runner.maintenance_due(now=_local_now(5, 59)) == {}
    assert runner.maintenance_due(now=_local_now(6, 1)) == {farm.id: JobStatus.ok}
    assert runner.maintenance_due(now=_local_now(9, 0)) == {}
    runs = _runs(db, runner.MAINTENANCE_DUE, farm)
    assert [run.message for run in runs] == ["due=1 overdue=1"]

    # A farm without a location is skipped (recorded, not an error).
    farm.location = None
    db.commit()
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", _Feed([]))
    assert runner.service_refresh() == {farm.id: JobStatus.ok}
    assert _runs(db, runner.SERVICE_REFRESH, farm)[0].message == "skipped.location_required"


def test_daily_tick_and_prune(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    farm = _farm(make_user, make_farm, "jobs-tick@agrect.app")
    monkeypatch.setattr(get_settings(), "history_years", 1)
    monkeypatch.setattr(
        "app.modules.weather.service.fetch_archive",
        lambda *_args: [],
    )
    old = datetime.now(UTC) - timedelta(days=31)
    db.add(
        JobRun(
            job=runner.SERVICE_REFRESH,
            farm_id=farm.id,
            started_at=old,
            finished_at=old,
            status=JobStatus.ok,
        )
    )
    db.commit()

    runner.daily_tick(now=_local_now(7, 0))
    db.expire_all()
    jobs = {run.job for run in db.scalars(select(JobRun).where(JobRun.farm_id == farm.id))}
    assert jobs == {runner.DERIVE_DAILY, runner.HISTORY_BACKFILL, runner.MAINTENANCE_DUE}
    assert (
        db.scalar(
            select(func.count())
            .select_from(JobRun)
            .where(JobRun.started_at < old + timedelta(minutes=1))
        )
        == 0
    )


def test_jobs_status_endpoint_and_scoping(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = make_user("jobs-status@agrect.app", "password-jobs")
    farm = make_farm(owner, "Status farm", Decimal("36.5"), Decimal("3.2"))
    other = make_user("jobs-other@agrect.app", "password-jobs")
    yesterday = datetime.now(ZONE).date() - timedelta(days=1)
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", _Feed(_hours_for(yesterday)))
    runner.service_refresh()

    status = client.get(f"/v1/farms/{farm.id}/jobs/status", headers=auth_header(owner))
    assert status.status_code == 200, status.text
    by_job = {item["job"]: item["last_run"] for item in status.json()["jobs"]}
    assert list(by_job) == list(runner.JOB_NAMES)
    assert by_job[runner.SERVICE_REFRESH]["status"] == "ok"
    assert by_job[runner.DERIVE_DAILY] is None

    hidden = client.get(f"/v1/farms/{farm.id}/jobs/status", headers=auth_header(other))
    assert hidden.status_code == 404
