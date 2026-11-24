import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentFarm, CurrentUser, Db
from app.modules.station.models import CapacityMode
from app.modules.station.schemas import (
    BlocksPut,
    CapacityCheckOut,
    CapacityDecisionIn,
    CapacityDecisionOut,
    FarmStationOut,
    PumpIn,
    PumpOut,
    PumpPatch,
    WaterSourceIn,
    WaterSourceOut,
    WaterSourcePatch,
    WindowsPut,
)
from app.modules.station.service import (
    create_pump,
    create_water_source,
    delete_pump,
    delete_water_source,
    list_water_sources,
    read_capacity_check,
    read_station,
    record_capacity_decision,
    replace_blocks,
    replace_windows,
    update_pump,
    update_water_source,
)

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["station"])
pump_router = APIRouter(prefix="/pumps", tags=["station"])
source_router = APIRouter(prefix="/water-sources", tags=["station"])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@farm_router.get("/station", response_model=FarmStationOut)
def get_station(farm: CurrentFarm, db: Db) -> FarmStationOut:
    return read_station(db, farm)


@farm_router.post("/station/pumps", status_code=201, response_model=PumpOut)
def post_pump(body: PumpIn, farm: CurrentFarm, db: Db, response: Response) -> PumpOut:
    saved = create_pump(db, farm, body)
    _etag(response, saved.version)
    return saved


@pump_router.patch("/{pump_id}", response_model=PumpOut)
def patch_pump(
    pump_id: uuid.UUID,
    body: PumpPatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> PumpOut:
    saved = update_pump(db, user, pump_id, body, if_match)
    _etag(response, saved.version)
    return saved


@pump_router.delete("/{pump_id}", status_code=204)
def remove_pump(
    pump_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_pump(db, user, pump_id, if_match)
    return Response(status_code=204)


@pump_router.put("/{pump_id}/windows", response_model=PumpOut)
def put_windows(
    pump_id: uuid.UUID,
    body: WindowsPut,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> PumpOut:
    saved = replace_windows(db, user, pump_id, body, if_match)
    _etag(response, saved.version)
    return saved


@pump_router.put("/{pump_id}/blocks", response_model=PumpOut)
def put_blocks(
    pump_id: uuid.UUID,
    body: BlocksPut,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> PumpOut:
    saved = replace_blocks(db, user, pump_id, body, if_match)
    _etag(response, saved.version)
    return saved


@farm_router.get("/water-sources", response_model=list[WaterSourceOut])
def get_water_sources(farm: CurrentFarm, db: Db) -> list[WaterSourceOut]:
    return list_water_sources(db, farm)


@farm_router.post("/water-sources", status_code=201, response_model=WaterSourceOut)
def post_water_source(body: WaterSourceIn, farm: CurrentFarm, db: Db) -> WaterSourceOut:
    return create_water_source(db, farm, body)


@source_router.patch("/{source_id}", response_model=WaterSourceOut)
def patch_water_source(
    source_id: uuid.UUID,
    body: WaterSourcePatch,
    user: CurrentUser,
    db: Db,
) -> WaterSourceOut:
    return update_water_source(db, user, source_id, body)


@source_router.delete("/{source_id}", status_code=204)
def remove_water_source(source_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    delete_water_source(db, user, source_id)
    return Response(status_code=204)


@farm_router.get("/capacity-check", response_model=CapacityCheckOut)
def get_capacity_check(
    farm: CurrentFarm,
    db: Db,
    mode: Annotated[CapacityMode, Query()] = CapacityMode.today,
) -> CapacityCheckOut:
    return read_capacity_check(db, farm, mode)


@farm_router.post("/capacity-decisions", status_code=201, response_model=CapacityDecisionOut)
def post_capacity_decision(
    body: CapacityDecisionIn,
    farm: CurrentFarm,
    user: CurrentUser,
    db: Db,
) -> CapacityDecisionOut:
    return record_capacity_decision(db, farm, user, body)
