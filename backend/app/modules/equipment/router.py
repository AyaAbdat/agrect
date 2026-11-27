import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentFarm, CurrentUser, Db
from app.modules.equipment.schemas import (
    MachineDetailOut,
    MachineIn,
    MachineListOut,
    MachineOut,
    MachinePatch,
    MaintenanceDoneIn,
    MaintenanceIn,
    MaintenanceListOut,
    MaintenanceOut,
    MaintenancePatch,
)
from app.modules.equipment.service import (
    create_machine,
    create_maintenance,
    delete_machine,
    delete_maintenance,
    farm_maintenance_due,
    get_machine,
    list_machines,
    list_maintenance,
    mark_maintenance_done,
    update_machine,
    update_maintenance,
)

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["equipment"])
machine_router = APIRouter(prefix="/machines", tags=["equipment"])
maintenance_router = APIRouter(prefix="/maintenance", tags=["equipment"])

IfMatch = Annotated[str | None, Header(alias="If-Match")]


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@farm_router.get("/machines", response_model=MachineListOut)
def get_machines(farm: CurrentFarm, db: Db) -> MachineListOut:
    return list_machines(db, farm)


@farm_router.post("/machines", response_model=MachineOut, status_code=201)
def post_machine(
    body: MachineIn, farm: CurrentFarm, user: CurrentUser, db: Db, response: Response
) -> MachineOut:
    saved = create_machine(db, farm, user, body)
    _etag(response, saved.version)
    return saved


@farm_router.get("/maintenance/due", response_model=MaintenanceListOut)
def get_maintenance_due(farm: CurrentFarm, db: Db) -> MaintenanceListOut:
    return farm_maintenance_due(db, farm)


@machine_router.get("/{machine_id}", response_model=MachineDetailOut)
def get_machine_detail(
    machine_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    response: Response,
    season: Annotated[int | None, Query()] = None,
) -> MachineDetailOut:
    detail = get_machine(db, user, machine_id, season)
    _etag(response, detail.version)
    return detail


@machine_router.patch("/{machine_id}", response_model=MachineOut)
def patch_machine(
    machine_id: uuid.UUID,
    body: MachinePatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: IfMatch = None,
) -> MachineOut:
    saved = update_machine(db, user, machine_id, body, if_match)
    _etag(response, saved.version)
    return saved


@machine_router.delete("/{machine_id}", status_code=204)
def remove_machine(
    machine_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    reason: Annotated[str | None, Query()] = None,
    if_match: IfMatch = None,
) -> Response:
    delete_machine(db, user, machine_id, if_match, reason)
    return Response(status_code=204)


@machine_router.get("/{machine_id}/maintenance", response_model=MaintenanceListOut)
def get_machine_maintenance(machine_id: uuid.UUID, user: CurrentUser, db: Db) -> MaintenanceListOut:
    return list_maintenance(db, user, machine_id)


@machine_router.post("/{machine_id}/maintenance", response_model=MaintenanceOut, status_code=201)
def post_machine_maintenance(
    machine_id: uuid.UUID,
    body: MaintenanceIn,
    user: CurrentUser,
    db: Db,
    response: Response,
) -> MaintenanceOut:
    saved = create_maintenance(db, user, machine_id, body)
    _etag(response, saved.version)
    return saved


@maintenance_router.patch("/{maintenance_id}", response_model=MaintenanceOut)
def patch_maintenance(
    maintenance_id: uuid.UUID,
    body: MaintenancePatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: IfMatch = None,
) -> MaintenanceOut:
    saved = update_maintenance(db, user, maintenance_id, body, if_match)
    _etag(response, saved.version)
    return saved


@maintenance_router.post("/{maintenance_id}/done", response_model=MaintenanceOut)
def post_maintenance_done(
    maintenance_id: uuid.UUID,
    body: MaintenanceDoneIn,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: IfMatch = None,
) -> MaintenanceOut:
    saved = mark_maintenance_done(db, user, maintenance_id, body, if_match)
    _etag(response, saved.version)
    return saved


@maintenance_router.delete("/{maintenance_id}", status_code=204)
def remove_maintenance(
    maintenance_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    reason: Annotated[str | None, Query()] = None,
    if_match: IfMatch = None,
) -> Response:
    delete_maintenance(db, user, maintenance_id, if_match, reason)
    return Response(status_code=204)
