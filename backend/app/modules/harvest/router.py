import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from app.core.deps import CurrentBlock, CurrentFarm, CurrentUser, Db
from app.core.security import get_current_user
from app.modules.harvest.schemas import (
    HarvestEntryIn,
    HarvestEntryOut,
    HarvestEntryPatch,
    HarvestFarmSummaryOut,
    HarvestFieldsOut,
    HarvestListOut,
    HarvestPreviewIn,
    HarvestPreviewOut,
)
from app.modules.harvest.service import (
    create_entry,
    delete_entry,
    farm_summary,
    harvest_fields,
    list_entries,
    preview_harvest,
    update_entry,
)

router = APIRouter(prefix="/blocks/{block_id}", tags=["harvest"])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@router.get("/harvest", response_model=HarvestListOut)
def get_harvest(block: CurrentBlock, db: Db) -> HarvestListOut:
    return list_entries(db, block)


@router.post("/harvest", response_model=HarvestEntryOut, status_code=201)
def post_harvest(
    body: HarvestEntryIn,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
) -> HarvestEntryOut:
    saved = create_entry(db, block, user, body)
    _etag(response, saved.version)
    return saved


@router.patch("/harvest/{entry_id}", response_model=HarvestEntryOut)
def patch_harvest(
    entry_id: uuid.UUID,
    body: HarvestEntryPatch,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> HarvestEntryOut:
    saved = update_entry(db, block, user, entry_id, body, if_match)
    _etag(response, saved.version)
    return saved


@router.delete("/harvest/{entry_id}", status_code=204)
def remove_harvest(
    entry_id: uuid.UUID,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_entry(db, block, user, entry_id, if_match)
    return Response(status_code=204)


farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["harvest"])


@farm_router.get("/harvest/summary", response_model=HarvestFarmSummaryOut)
def get_harvest_summary(
    farm: CurrentFarm,
    db: Db,
    season: Annotated[int, Query()],
) -> HarvestFarmSummaryOut:
    return farm_summary(db, farm, season)


catalog_router = APIRouter(
    prefix="/catalog",
    tags=["harvest"],
    dependencies=[Depends(get_current_user)],
)


@catalog_router.get("/crops/{crop_id}/harvest-fields", response_model=HarvestFieldsOut)
def get_harvest_fields(crop_id: uuid.UUID, db: Db) -> HarvestFieldsOut:
    return harvest_fields(db, crop_id)


calc_router = APIRouter(prefix="/calc", tags=["harvest"])


@calc_router.post("/harvest", response_model=HarvestPreviewOut)
def post_harvest_preview(
    body: HarvestPreviewIn,
    user: CurrentUser,
    db: Db,
) -> HarvestPreviewOut:
    return preview_harvest(db, user, body)
