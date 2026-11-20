import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import CurrentFarm, CurrentUser, Db
from app.core.errors import AppError
from app.core.security import get_current_user
from app.modules.catalog.models import Crop, SoilTextureClass, TrainingSystem, Variety
from app.modules.catalog.schemas import (
    CropOut,
    CropStagesOut,
    LocalizedName,
    SoilTextureOut,
    StageDdOut,
    StageDdPut,
    StagePrefsOut,
    StagePrefsPut,
    TrainingSystemOut,
    VarietyOut,
    format_theta,
)
from app.modules.catalog.service import (
    read_crop_stages,
    read_stage_dd,
    read_stage_prefs,
    write_stage_dd,
    write_stage_prefs,
)

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
    dependencies=[Depends(get_current_user)],
)


def _require_crop(db: Db, crop_id: uuid.UUID) -> Crop:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise AppError("catalog.crop_not_found", 404)
    return crop


@router.get("/crops", response_model=list[CropOut])
def list_crops(db: Db) -> list[CropOut]:
    rows = db.scalars(select(Crop).order_by(Crop.sort, Crop.code)).all()
    return [
        CropOut(
            id=row.id,
            code=row.code,
            kind=row.kind,
            name=LocalizedName(fr=row.name_fr, ar=row.name_ar, en=row.name_en),
        )
        for row in rows
    ]


@router.get("/crops/{crop_id}/varieties", response_model=list[VarietyOut])
def list_varieties(crop_id: uuid.UUID, db: Db) -> list[VarietyOut]:
    _require_crop(db, crop_id)
    rows = db.scalars(
        select(Variety).where(Variety.crop_id == crop_id).order_by(Variety.sort, Variety.code)
    ).all()
    return [VarietyOut(id=row.id, code=row.code, name=row.name) for row in rows]


@router.get("/crops/{crop_id}/training-systems", response_model=list[TrainingSystemOut])
def list_training_systems(crop_id: uuid.UUID, db: Db) -> list[TrainingSystemOut]:
    _require_crop(db, crop_id)
    rows = db.scalars(
        select(TrainingSystem)
        .where(TrainingSystem.crop_id == crop_id)
        .order_by(TrainingSystem.sort, TrainingSystem.code)
    ).all()
    return [
        TrainingSystemOut(
            id=row.id,
            code=row.code,
            name=LocalizedName(fr=row.name_fr, ar=row.name_ar, en=row.name_en),
            description=LocalizedName(
                fr=row.description_fr,
                ar=row.description_ar,
                en=row.description_en,
            ),
        )
        for row in rows
    ]


@router.get("/crops/{crop_id}/stages", response_model=CropStagesOut)
def list_stages(crop_id: uuid.UUID, db: Db) -> CropStagesOut:
    return read_crop_stages(db, crop_id)


@router.get("/soil-textures", response_model=list[SoilTextureOut])
def list_soil_textures(db: Db) -> list[SoilTextureOut]:
    rows = db.scalars(select(SoilTextureClass).order_by(SoilTextureClass.sort)).all()
    return [_soil_out(row) for row in rows]


def _soil_out(row: SoilTextureClass) -> SoilTextureOut:
    values = (
        row.theta_fc_min,
        row.theta_fc_max,
        row.theta_wp_min,
        row.theta_wp_max,
        row.theta_fc,
        row.theta_wp,
    )
    return SoilTextureOut(
        id=row.id,
        code=row.code,
        name=LocalizedName(fr=row.name_fr, ar=row.name_ar, en=row.name_en),
        theta_fc_min=format_theta(row.theta_fc_min),
        theta_fc_max=format_theta(row.theta_fc_max),
        theta_wp_min=format_theta(row.theta_wp_min),
        theta_wp_max=format_theta(row.theta_wp_max),
        theta_fc=format_theta(row.theta_fc),
        theta_wp=format_theta(row.theta_wp),
        citation=row.citation,
        source="entered" if all(value is not None for value in values) else None,
    )


farm_router = APIRouter(prefix="/farms/{farm_id}", tags=["phenology"])


@farm_router.get("/stage-dd", response_model=StageDdOut)
def get_stage_dd(farm: CurrentFarm, db: Db, crop_id: uuid.UUID) -> StageDdOut:
    return read_stage_dd(db, farm, crop_id)


@farm_router.put("/stage-dd", response_model=StageDdOut)
def put_stage_dd(body: StageDdPut, farm: CurrentFarm, user: CurrentUser, db: Db) -> StageDdOut:
    return write_stage_dd(db, farm, user, body)


@farm_router.get("/stage-prefs", response_model=StagePrefsOut)
def get_stage_prefs(farm: CurrentFarm, db: Db, crop_id: uuid.UUID) -> StagePrefsOut:
    return read_stage_prefs(db, farm, crop_id)


@farm_router.put("/stage-prefs", response_model=StagePrefsOut)
def put_stage_prefs(body: StagePrefsPut, farm: CurrentFarm, db: Db) -> StagePrefsOut:
    return write_stage_prefs(db, farm, body)
