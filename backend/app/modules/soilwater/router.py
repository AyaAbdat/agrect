import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentBlock, CurrentFarm, CurrentUser, Db
from app.modules.soilwater.schemas import (
    BalancePeriod,
    FarmIrrigationTodayOut,
    IrrigationEventIn,
    IrrigationEventOut,
    IrrigationEventPatch,
    IrrigationEventsOut,
    IrrigationPreviewIn,
    IrrigationPreviewOut,
    IrrigationSettingsOut,
    IrrigationSettingsPut,
    IrrigationTodayOut,
    SoilCheckIn,
    SoilCheckOut,
    SoilCheckPreviewIn,
    SoilCheckPreviewOut,
    SoilOut,
    SoilPut,
    WaterBalanceOut,
)
from app.modules.soilwater.service import (
    create_irrigation_event,
    create_soil_check,
    delete_irrigation_event,
    list_irrigation_events,
    preview_irrigation,
    preview_soil_check,
    read_farm_irrigation_today,
    read_irrigation_today,
    read_settings,
    read_soil,
    read_water_balance,
    save_settings,
    save_soil,
    update_irrigation_event,
)

router = APIRouter(prefix="/blocks/{block_id}", tags=["soilwater"])


def _etag(response: Response, version: int | None) -> None:
    if version is not None:
        response.headers["ETag"] = str(version)


@router.get("/soil", response_model=SoilOut)
def get_soil(block: CurrentBlock, db: Db, response: Response) -> SoilOut:
    body = read_soil(db, block)
    _etag(response, body.version)
    return body


@router.put("/soil", response_model=SoilOut)
def put_soil(
    body: SoilPut,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> SoilOut:
    saved = save_soil(db, block, user, body, if_match)
    _etag(response, saved.version)
    return saved


@router.get("/irrigation-settings", response_model=IrrigationSettingsOut)
def get_irrigation_settings(
    block: CurrentBlock,
    db: Db,
    response: Response,
) -> IrrigationSettingsOut:
    body = read_settings(db, block)
    _etag(response, body.version)
    return body


@router.put("/irrigation-settings", response_model=IrrigationSettingsOut)
def put_irrigation_settings(
    body: IrrigationSettingsPut,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> IrrigationSettingsOut:
    saved = save_settings(db, block, user, body, if_match)
    _etag(response, saved.version)
    return saved


@router.get("/irrigation-events", response_model=IrrigationEventsOut)
def get_irrigation_events(
    block: CurrentBlock,
    db: Db,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int | None, Query(ge=1, le=500)] = None,
) -> IrrigationEventsOut:
    return list_irrigation_events(db, block, from_date, to_date, limit)


@router.post("/irrigation-events", response_model=IrrigationEventOut)
def post_irrigation_event(
    body: IrrigationEventIn,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
) -> IrrigationEventOut:
    saved = create_irrigation_event(db, block, user, body)
    _etag(response, saved.version)
    return saved


@router.patch("/irrigation-events/{event_id}", response_model=IrrigationEventOut)
def patch_irrigation_event(
    event_id: uuid.UUID,
    body: IrrigationEventPatch,
    block: CurrentBlock,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> IrrigationEventOut:
    saved = update_irrigation_event(db, block, event_id, body, if_match)
    _etag(response, saved.version)
    return saved


@router.delete("/irrigation-events/{event_id}", status_code=204)
def remove_irrigation_event(
    event_id: uuid.UUID,
    block: CurrentBlock,
    db: Db,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_irrigation_event(db, block, event_id, if_match)
    return Response(status_code=204)


@router.post("/soil-checks/preview", response_model=SoilCheckPreviewOut)
def post_soil_check_preview(
    body: SoilCheckPreviewIn,
    block: CurrentBlock,
    db: Db,
) -> SoilCheckPreviewOut:
    return preview_soil_check(db, block, body.feel)


@router.post("/soil-checks", response_model=SoilCheckOut)
def post_soil_check(body: SoilCheckIn, block: CurrentBlock, db: Db) -> SoilCheckOut:
    return create_soil_check(db, block, body)


@router.get("/water-balance", response_model=WaterBalanceOut)
def get_water_balance(
    block: CurrentBlock,
    db: Db,
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    period: Annotated[BalancePeriod | None, Query()] = None,
) -> WaterBalanceOut:
    return read_water_balance(db, block, from_date, to_date, period)


@router.get("/irrigation-today", response_model=IrrigationTodayOut)
def get_irrigation_today(block: CurrentBlock, db: Db) -> IrrigationTodayOut:
    return read_irrigation_today(db, block)


farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["soilwater"])


@farm_router.get("/irrigation-today", response_model=FarmIrrigationTodayOut)
def get_farm_irrigation_today(farm: CurrentFarm, db: Db) -> FarmIrrigationTodayOut:
    return read_farm_irrigation_today(db, farm)


calc_router = APIRouter(prefix="/calc/soilwater", tags=["soilwater"])


@calc_router.post("/irrigation", response_model=IrrigationPreviewOut)
def post_irrigation_preview(
    body: IrrigationPreviewIn,
    user: CurrentUser,
    db: Db,
) -> IrrigationPreviewOut:
    return preview_irrigation(db, user, body)
