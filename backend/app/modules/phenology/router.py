import uuid

from fastapi import APIRouter, Response

from app.core.deps import CurrentBlock, CurrentFarm, CurrentUser, Db
from app.modules.phenology.schemas import (
    BlockStagesOut,
    ObservationIn,
    ObservationOut,
    SeasonOut,
    SeasonPut,
    StageSummaryOut,
)
from app.modules.phenology.service import (
    add_observation,
    delete_observation,
    owned_season,
    read_block_stages,
    read_farm_summary,
    read_season,
    write_season,
)

blocks_router = APIRouter(prefix="/blocks", tags=["phenology"])
seasons_router = APIRouter(prefix="/block-seasons", tags=["phenology"])
farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["phenology"])


@blocks_router.get("/{block_id}/seasons/{year}", response_model=SeasonOut)
def get_season(year: int, block: CurrentBlock, db: Db) -> SeasonOut:
    return read_season(db, block, year)


@blocks_router.put("/{block_id}/seasons/{year}", response_model=SeasonOut)
def put_season(year: int, body: SeasonPut, block: CurrentBlock, db: Db) -> SeasonOut:
    return write_season(db, block, year, body)


@blocks_router.get("/{block_id}/stages", response_model=BlockStagesOut)
def get_stages(year: int, block: CurrentBlock, db: Db) -> BlockStagesOut:
    return read_block_stages(db, block, year)


@seasons_router.post(
    "/{season_id}/observations",
    status_code=201,
    response_model=ObservationOut,
)
def post_observation(
    season_id: uuid.UUID,
    body: ObservationIn,
    user: CurrentUser,
    db: Db,
) -> ObservationOut:
    season = owned_season(db, user, season_id)
    return add_observation(db, user, season, body)


@seasons_router.delete("/{season_id}/observations/{obs_id}", status_code=204)
def remove_observation(
    season_id: uuid.UUID,
    obs_id: uuid.UUID,
    user: CurrentUser,
    db: Db,
) -> Response:
    season = owned_season(db, user, season_id)
    delete_observation(db, season, obs_id)
    return Response(status_code=204)


@farm_router.get("/stages/summary", response_model=StageSummaryOut)
def get_stage_summary(crop_id: uuid.UUID, farm: CurrentFarm, db: Db) -> StageSummaryOut:
    return read_farm_summary(db, farm, crop_id)
