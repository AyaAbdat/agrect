import uuid
from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentBlock, CurrentFarm, CurrentUser, Db
from app.modules.operations.schemas import (
    JournalListOut,
    OperationIn,
    OperationListOut,
    OperationOut,
    OperationPatch,
    OperationProductPreviewIn,
    OperationProductPreviewOut,
    ProductIn,
    ProductListOut,
    ProductOut,
    ProductPatch,
    ReentryOut,
    StageAtOut,
)
from app.modules.operations.service import (
    block_reentry,
    create_operation,
    create_product,
    delete_operation,
    delete_product,
    get_operation,
    list_journal,
    list_operations,
    list_products,
    preview_operation_product,
    stage_at,
    update_operation,
    update_product,
)

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["operations"])
product_router = APIRouter(prefix="/products", tags=["operations"])
operation_router = APIRouter(prefix="/operations", tags=["operations"])
blocks_router = APIRouter(prefix="/blocks/{block_id}", tags=["operations"])
calc_router = APIRouter(prefix="/calc", tags=["operations"])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@farm_router.get("/products", response_model=ProductListOut)
def get_products(farm: CurrentFarm, db: Db) -> ProductListOut:
    return list_products(db, farm)


@farm_router.post("/products", response_model=ProductOut, status_code=201)
def post_product(
    body: ProductIn,
    farm: CurrentFarm,
    user: CurrentUser,
    db: Db,
    response: Response,
) -> ProductOut:
    saved = create_product(db, farm, user, body)
    _etag(response, saved.version)
    return saved


@product_router.patch("/{product_id}", response_model=ProductOut)
def patch_product(
    product_id: uuid.UUID,
    body: ProductPatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ProductOut:
    saved = update_product(db, user, product_id, body, if_match)
    _etag(response, saved.version)
    return saved


@product_router.delete("/{product_id}", status_code=204)
def remove_product(
    product_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_product(db, user, product_id, if_match)
    return Response(status_code=204)


@farm_router.get("/operations", response_model=OperationListOut)
def get_operations(
    farm: CurrentFarm,
    db: Db,
    block_id: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[Date | None, Query(alias="from")] = None,
    date_to: Annotated[Date | None, Query(alias="to")] = None,
) -> OperationListOut:
    return list_operations(db, farm, block_id=block_id, date_from=date_from, date_to=date_to)


@farm_router.post("/operations", response_model=OperationOut, status_code=201)
def post_operation(
    body: OperationIn,
    farm: CurrentFarm,
    user: CurrentUser,
    db: Db,
    response: Response,
) -> OperationOut:
    saved = create_operation(db, farm, user, body)
    _etag(response, saved.version)
    return saved


@operation_router.get("/{operation_id}", response_model=OperationOut)
def read_operation(operation_id: uuid.UUID, user: CurrentUser, db: Db) -> OperationOut:
    return get_operation(db, user, operation_id)


@operation_router.patch("/{operation_id}", response_model=OperationOut)
def patch_operation(
    operation_id: uuid.UUID,
    body: OperationPatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> OperationOut:
    saved = update_operation(db, user, operation_id, body, if_match)
    _etag(response, saved.version)
    return saved


@operation_router.delete("/{operation_id}", status_code=204)
def remove_operation(
    operation_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_operation(db, user, operation_id, if_match)
    return Response(status_code=204)


@blocks_router.get("/reentry", response_model=ReentryOut | None)
def get_reentry(block: CurrentBlock, db: Db) -> ReentryOut | None:
    return block_reentry(db, block)


@blocks_router.get("/journal", response_model=JournalListOut)
def get_journal(
    block: CurrentBlock,
    db: Db,
    date_from: Annotated[Date | None, Query(alias="from")] = None,
    date_to: Annotated[Date | None, Query(alias="to")] = None,
    types: Annotated[str | None, Query()] = None,
) -> JournalListOut:
    return list_journal(db, block, date_from=date_from, date_to=date_to, types=types)


@blocks_router.get("/stage-at", response_model=StageAtOut)
def get_stage_at(
    block: CurrentBlock,
    db: Db,
    on: Annotated[Date, Query(alias="date")],
) -> StageAtOut:
    return stage_at(db, block, on)


@calc_router.post("/operation-product", response_model=OperationProductPreviewOut)
def post_operation_product_preview(body: OperationProductPreviewIn) -> OperationProductPreviewOut:
    return preview_operation_product(body)
