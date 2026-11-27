import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Query, Response

from app.core.deps import CurrentBlock, CurrentFarm, CurrentUser, Db
from app.modules.inputs.schemas import (
    BlockCostsOut,
    FarmCostsOut,
    PriceIn,
    PriceListOut,
    PriceOut,
    PricePatch,
    StockMoveIn,
    StockMoveListOut,
    StockMoveOut,
    StockOut,
)
from app.modules.inputs.service import (
    block_costs,
    create_price,
    create_stock_move,
    delete_price,
    delete_stock_move,
    farm_costs,
    get_stock,
    list_prices,
    list_stock_moves,
    update_price,
)

farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["inputs"])
price_router = APIRouter(prefix="/prices", tags=["inputs"])
stock_move_router = APIRouter(prefix="/stock-moves", tags=["inputs"])
blocks_router = APIRouter(prefix="/blocks/{block_id}", tags=["inputs"])


def _etag(response: Response, version: int) -> None:
    response.headers["ETag"] = str(version)


@farm_router.get("/prices", response_model=PriceListOut)
def get_prices(farm: CurrentFarm, db: Db) -> PriceListOut:
    return list_prices(db, farm)


@farm_router.post("/prices", response_model=PriceOut, status_code=201)
def post_price(
    body: PriceIn, farm: CurrentFarm, user: CurrentUser, db: Db, response: Response
) -> PriceOut:
    saved = create_price(db, farm, user, body)
    _etag(response, saved.version)
    return saved


@price_router.patch("/{price_id}", response_model=PriceOut)
def patch_price(
    price_id: uuid.UUID,
    body: PricePatch,
    user: CurrentUser,
    db: Db,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> PriceOut:
    saved = update_price(db, user, price_id, body, if_match)
    _etag(response, saved.version)
    return saved


@price_router.delete("/{price_id}", status_code=204)
def remove_price(
    price_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
    reason: Annotated[str | None, Query()] = None,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> Response:
    delete_price(db, user, price_id, if_match, reason)
    return Response(status_code=204)


@farm_router.get("/stock-moves", response_model=StockMoveListOut)
def get_stock_moves(farm: CurrentFarm, db: Db) -> StockMoveListOut:
    return list_stock_moves(db, farm)


@farm_router.post("/stock-moves", response_model=StockMoveOut, status_code=201)
def post_stock_move(
    body: StockMoveIn, farm: CurrentFarm, user: CurrentUser, db: Db
) -> StockMoveOut:
    return create_stock_move(db, farm, user, body)


@stock_move_router.delete("/{move_id}", status_code=204)
def remove_stock_move(move_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    delete_stock_move(db, user, move_id)
    return Response(status_code=204)


@farm_router.get("/stock", response_model=StockOut)
def get_farm_stock(farm: CurrentFarm, db: Db) -> StockOut:
    return get_stock(db, farm)


@farm_router.get("/costs", response_model=FarmCostsOut)
def get_farm_costs(
    farm: CurrentFarm,
    db: Db,
    season: Annotated[int | None, Query()] = None,
) -> FarmCostsOut:
    return farm_costs(db, farm, season)


@blocks_router.get("/costs", response_model=BlockCostsOut)
def get_block_costs(
    block: CurrentBlock,
    db: Db,
    season: Annotated[int | None, Query()] = None,
) -> BlockCostsOut:
    return block_costs(db, block, season)
