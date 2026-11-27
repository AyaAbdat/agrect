"""In-process APScheduler, started from the FastAPI lifespan when JOBS_ENABLED is true.

Every worker process that has JOBS_ENABLED runs a supervisor; only the one holding
a Postgres session advisory lock (on its own dedicated connection) runs the work
jobs. Postgres lets one session hold the lock, so there are never two holders.

- The holder checks its lock connection (``SELECT 1``) before every work tick and
  every 5 minutes. If the check fails it pauses the work jobs, opens a new
  connection and tries the lock again; it resumes only if it gets the lock.
- A worker without the lock keeps its work jobs paused and tries the lock every
  5 minutes, so if the holder dies another worker takes over.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import Connection, text

from app.core.config import Settings
from app.core.db import engine
from app.jobs import runner

logger = logging.getLogger(__name__)

# Arbitrary constant identifying "AGRECT background jobs" among advisory locks.
JOBS_LOCK_KEY = 4_712_036_001
LOCK_JOB_ID = "jobs_lock"
DAILY_TICK_ID = "daily_tick"
WORK_JOB_IDS = (runner.SERVICE_REFRESH, DAILY_TICK_ID)
LOCK_RETRY_MINUTES = 5


class JobsSupervisor:
    """Owns the scheduler and the advisory lock of one worker process."""

    def __init__(self, connect: Callable[[], Connection] = engine.connect) -> None:
        self._connect = connect
        self._connection: Connection | None = None
        self._guard = threading.RLock()
        self.scheduler = BackgroundScheduler(
            timezone="UTC",
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600},
        )

    @property
    def holds_lock(self) -> bool:
        return self._connection is not None

    def work_jobs_paused(self) -> bool:
        jobs = [self.scheduler.get_job(job_id) for job_id in WORK_JOB_IDS]
        return all(job is not None and job.next_run_time is None for job in jobs)

    # --- lock ---------------------------------------------------------------

    def _try_acquire(self) -> bool:
        try:
            connection = self._connect()
        except Exception:
            logger.warning("jobs lock: cannot open a connection", exc_info=True)
            return False
        try:
            taken = connection.scalar(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": JOBS_LOCK_KEY}
            )
            # End the read transaction; a session advisory lock outlives it.
            connection.commit()
        except Exception:
            logger.warning("jobs lock: try failed", exc_info=True)
            _close_quietly(connection)
            return False
        if not taken:
            _close_quietly(connection)
            return False
        self._connection = connection
        return True

    def _alive(self) -> bool:
        connection = self._connection
        if connection is None:
            return False
        try:
            connection.execute(text("SELECT 1"))
            connection.commit()
        except Exception:
            logger.warning("jobs lock: lock connection lost", exc_info=True)
            return False
        return True

    def _set_paused(self, paused: bool) -> None:
        for job_id in WORK_JOB_IDS:
            if self.scheduler.get_job(job_id) is None:
                continue
            if paused:
                self.scheduler.pause_job(job_id)
            else:
                self.scheduler.resume_job(job_id)

    def ensure_lock(self) -> bool:
        """True when this process holds the lock (checked now); pauses or resumes work jobs."""
        with self._guard:
            if self._connection is not None:
                if self._alive():
                    return True
                _close_quietly(self._connection)
                self._connection = None
                self._set_paused(True)
            if self._try_acquire():
                logger.info("jobs lock taken; this process runs the background jobs")
                self._set_paused(False)
                return True
            self._set_paused(True)
            return False

    # --- jobs ---------------------------------------------------------------

    def _guarded(self, work: Callable[[], object]) -> Callable[[], None]:
        def run() -> None:
            if not self.ensure_lock():
                return
            work()

        run.__name__ = getattr(work, "__name__", "work")
        return run

    def _add_jobs(self) -> None:
        self.scheduler.add_job(
            self._guarded(runner.service_refresh),
            CronTrigger(minute=5, timezone="UTC"),
            id=runner.SERVICE_REFRESH,
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._guarded(runner.daily_tick),
            CronTrigger(minute="*/15", timezone="UTC"),
            id=DAILY_TICK_ID,
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.ensure_lock,
            IntervalTrigger(minutes=LOCK_RETRY_MINUTES, timezone="UTC"),
            id=LOCK_JOB_ID,
            replace_existing=True,
        )

    def start(self, *, paused: bool = False) -> None:
        self._add_jobs()
        self.scheduler.start(paused=paused)
        if not self.ensure_lock():
            logger.info("background jobs run in another process; retrying the lock every 5 min")

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        with self._guard:
            connection = self._connection
            self._connection = None
        if connection is None:
            return
        try:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": JOBS_LOCK_KEY})
            connection.commit()
        except Exception:
            logger.warning("jobs lock: unlock failed", exc_info=True)
        finally:
            _close_quietly(connection)


def _close_quietly(connection: Connection) -> None:
    try:
        connection.close()
    except Exception:
        logger.debug("closing a lost connection failed", exc_info=True)


def start_scheduler(*, paused: bool = False) -> JobsSupervisor:
    """Start this worker's supervisor; it runs the work jobs only while holding the lock.

    ``paused`` keeps every trigger from firing (tests); lock checks still run on call.
    """
    supervisor = JobsSupervisor()
    supervisor.start(paused=paused)
    logger.info(
        "background jobs supervisor started at %s (lock held: %s)",
        datetime.now(UTC).isoformat(),
        supervisor.holds_lock,
    )
    return supervisor


def start_jobs_if_enabled(settings: Settings, *, paused: bool = False) -> JobsSupervisor | None:
    """Lifespan entry: nothing starts unless JOBS_ENABLED is true."""
    if not settings.jobs_enabled:
        return None
    return start_scheduler(paused=paused)


def stop_scheduler(supervisor: JobsSupervisor) -> None:
    """Stop the jobs and release the advisory lock."""
    supervisor.stop()
