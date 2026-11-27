from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentFarm, Db
from app.jobs.models import JobRun, JobStatus
from app.jobs.runner import JOB_NAMES
from app.modules.operations.schemas import ApiModel

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["jobs"])


class JobRunOut(ApiModel):
    started_at: datetime
    finished_at: datetime | None
    status: JobStatus
    message: str | None


class JobStatusItemOut(ApiModel):
    job: str
    last_run: JobRunOut | None


class JobStatusOut(ApiModel):
    jobs: list[JobStatusItemOut]


@farm_router.get("/jobs/status", response_model=JobStatusOut)
def get_jobs_status(farm: CurrentFarm, db: Db) -> JobStatusOut:
    """Last run of each background job for this farm (owner only, via get_current_farm)."""
    items: list[JobStatusItemOut] = []
    for job in JOB_NAMES:
        row = db.scalars(
            select(JobRun)
            .where(JobRun.job == job, JobRun.farm_id == farm.id)
            .order_by(JobRun.started_at.desc())
            .limit(1)
        ).first()
        items.append(
            JobStatusItemOut(
                job=job,
                last_run=None
                if row is None
                else JobRunOut(
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                    status=row.status,
                    message=row.message,
                ),
            )
        )
    return JobStatusOut(jobs=items)
