from typing import Annotated

from fastapi import APIRouter, Header, Response

from app.core.deps import CurrentBlock, CurrentFarm, CurrentUser, Db
from app.modules.registry.schemas import (
    BlockArchive,
    BlockCreate,
    BlockHistoryOut,
    BlockListItem,
    BlockOut,
    BlockUpdate,
    IrrigationLayoutPut,
    PlantingsPut,
    ValvesPut,
)
from app.modules.registry.service import (
    archive_block,
    complete_block,
    create_block,
    list_blocks,
    list_history,
    replace_irrigation_layout,
    replace_plantings,
    replace_valves,
    to_block_out,
    update_block,
)

farm_blocks_router = APIRouter(prefix="/farms/{farm_id}/blocks", tags=["blocks"])
blocks_router = APIRouter(prefix="/blocks", tags=["blocks"])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@farm_blocks_router.post("", status_code=201, response_model=BlockOut)
def create_farm_block(
    body: BlockCreate,
    farm: CurrentFarm,
    db: Db,
    response: Response,
) -> BlockOut:
    block = create_block(db, farm, body)
    _etag(response, block.version)
    return to_block_out(db, block)


@farm_blocks_router.get("", response_model=list[BlockListItem])
def list_farm_blocks(
    farm: CurrentFarm,
    db: Db,
    include_archived: bool = False,
) -> list[BlockListItem]:
    return list_blocks(db, farm, include_archived=include_archived)


@blocks_router.get("/{block_id}", response_model=BlockOut)
def read_block(block: CurrentBlock, db: Db, response: Response) -> BlockOut:
    _etag(response, block.version)
    return to_block_out(db, block)


@blocks_router.patch("/{block_id}", response_model=BlockOut)
def patch_block(
    body: BlockUpdate,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlockOut:
    updated = update_block(db, block, user, body, if_match)
    _etag(response, updated.version)
    return to_block_out(db, updated)


@blocks_router.get("/{block_id}/history", response_model=list[BlockHistoryOut])
def read_block_history(block: CurrentBlock, db: Db) -> list[BlockHistoryOut]:
    return list_history(db, block)


@blocks_router.put("/{block_id}/plantings", response_model=BlockOut)
def put_plantings(
    body: PlantingsPut,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlockOut:
    updated = replace_plantings(db, block, user, body, if_match)
    _etag(response, updated.version)
    return to_block_out(db, updated)


@blocks_router.put("/{block_id}/irrigation-layout", response_model=BlockOut)
def put_irrigation_layout(
    body: IrrigationLayoutPut,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlockOut:
    updated = replace_irrigation_layout(db, block, user, body, if_match)
    _etag(response, updated.version)
    return to_block_out(db, updated)


@blocks_router.put("/{block_id}/valves", response_model=BlockOut)
def put_valves(
    body: ValvesPut,
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlockOut:
    updated = replace_valves(db, block, user, body, if_match)
    _etag(response, updated.version)
    return to_block_out(db, updated)


@blocks_router.post("/{block_id}/complete", response_model=BlockOut)
def complete_farm_block(
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> BlockOut:
    updated = complete_block(db, block, user, if_match)
    _etag(response, updated.version)
    return to_block_out(db, updated)


@blocks_router.post("/{block_id}/archive", response_model=BlockOut)
def archive_farm_block(
    block: CurrentBlock,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    body: BlockArchive | None = None,
) -> BlockOut:
    updated = archive_block(
        db,
        block,
        user,
        if_match,
        None if body is None else body.reason,
    )
    _etag(response, updated.version)
    return to_block_out(db, updated)
