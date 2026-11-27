import uuid
from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentFarm, CurrentUser, Db
from app.modules.labour.schemas import (
    AttendanceDayOut,
    AttendancePut,
    AttendanceSummaryOut,
    LabourNormListOut,
    WorkerIn,
    WorkerListOut,
    WorkerOut,
    WorkerPatch,
)
from app.modules.labour.service import (
    attendance_summary,
    create_worker,
    delete_worker,
    get_attendance,
    labour_norms,
    list_workers,
    put_attendance,
    update_worker,
)

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["labour"])
worker_router = APIRouter(prefix="/workers", tags=["labour"])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@farm_router.get("/workers", response_model=WorkerListOut)
def get_workers(farm: CurrentFarm, db: Db) -> WorkerListOut:
    return list_workers(db, farm)


@farm_router.post("/workers", response_model=WorkerOut, status_code=201)
def post_worker(
    body: WorkerIn, farm: CurrentFarm, user: CurrentUser, db: Db, response: Response
) -> WorkerOut:
    saved = create_worker(db, farm, user, body)
    _etag(response, saved.version)
    return saved


@worker_router.patch("/{worker_id}", response_model=WorkerOut)
def patch_worker(
    worker_id: uuid.UUID,
    body: WorkerPatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> WorkerOut:
    saved = update_worker(db, user, worker_id, body, if_match)
    _etag(response, saved.version)
    return saved


@worker_router.delete("/{worker_id}", status_code=204)
def remove_worker(
    worker_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    reason: Annotated[str | None, Query()] = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_worker(db, user, worker_id, if_match, reason)
    return Response(status_code=204)


@farm_router.get("/attendance/summary", response_model=AttendanceSummaryOut)
def get_attendance_summary(
    farm: CurrentFarm,
    db: Db,
    date_from: Annotated[Date, Query(alias="from")],
    date_to: Annotated[Date, Query(alias="to")],
) -> AttendanceSummaryOut:
    return attendance_summary(db, farm, date_from, date_to)


@farm_router.get("/attendance", response_model=AttendanceDayOut)
def get_farm_attendance(
    farm: CurrentFarm,
    db: Db,
    date: Annotated[Date, Query()],
) -> AttendanceDayOut:
    return get_attendance(db, farm, date)


@farm_router.put("/attendance", response_model=AttendanceDayOut)
def put_farm_attendance(body: AttendancePut, farm: CurrentFarm, db: Db) -> AttendanceDayOut:
    return put_attendance(db, farm, body)


@farm_router.get("/labour-norms", response_model=LabourNormListOut)
def get_labour_norms(
    farm: CurrentFarm,
    db: Db,
    season: Annotated[int | None, Query()] = None,
) -> LabourNormListOut:
    return labour_norms(db, farm, season)
