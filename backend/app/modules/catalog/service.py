"""Phenology catalogue reads and farm stage overrides."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import AppUser
from app.modules.catalog.models import (
    Crop,
    CropScale,
    FarmStagePref,
    StageDd,
    StageDdSource,
    StageDef,
)
from app.modules.catalog.schemas import (
    CropStagesOut,
    LocalizedName,
    StageDdItemIn,
    StageDdOut,
    StageDdPut,
    StageDdStageOut,
    StageOut,
    StagePrefItemOut,
    StagePrefsOut,
    StagePrefsPut,
)
from app.modules.farms.models import Farm
from app.modules.registry.models import RecordVersion
from app.modules.weather.models import GddSetting

_STAGE_DD = "stage_dd"


def _names(fr: str, ar: str, en: str) -> LocalizedName:
    return LocalizedName(fr=fr, ar=ar, en=en)


def _require_crop(db: Session, crop_id: uuid.UUID) -> Crop:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise AppError("catalog.crop_not_found", 404)
    return crop


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped


def read_crop_stages(db: Session, crop_id: uuid.UUID) -> CropStagesOut:
    _require_crop(db, crop_id)
    scale = db.get(CropScale, crop_id)
    if scale is None:
        raise AppError("phenology.scale_not_found", 404)
    rows = db.scalars(
        select(StageDef).where(StageDef.crop_id == crop_id).order_by(StageDef.sort, StageDef.code)
    ).all()
    return CropStagesOut(
        scale=scale.scale,
        scale_citation=scale.citation,
        stages=[
            StageOut(
                id=row.id,
                code=row.code,
                sort=row.sort,
                name=_names(row.name_fr, row.name_ar, row.name_en),
                description=_names(row.description_fr, row.description_ar, row.description_en),
            )
            for row in rows
        ],
    )


def _stage_rows(db: Session, crop_id: uuid.UUID) -> list[StageDef]:
    return list(
        db.scalars(
            select(StageDef)
            .where(StageDef.crop_id == crop_id)
            .order_by(StageDef.sort, StageDef.code)
        ).all()
    )


def _empty_stage(stage: StageDef) -> StageDdStageOut:
    return StageDdStageOut(
        stage_def_id=stage.id,
        code=stage.code,
        sort=stage.sort,
        name=_names(stage.name_fr, stage.name_ar, stage.name_en),
        dd_value=None,
        base_c=None,
        upper_c=None,
        method=None,
        source=None,
        citation=None,
        label="not_enough_data",
    )


def _from_row(stage: StageDef, row: StageDd) -> StageDdStageOut:
    if row.farm_id is None:
        source = "farm_seasons" if row.source_kind == StageDdSource.farm_seasons else "literature"
        citation = row.citation
    else:
        source = "entered"
        citation = None
    return StageDdStageOut(
        stage_def_id=stage.id,
        code=stage.code,
        sort=stage.sort,
        name=_names(stage.name_fr, stage.name_ar, stage.name_en),
        dd_value=row.dd_value,
        base_c=row.base_c,
        upper_c=row.upper_c,
        method=row.method,
        source=source,
        citation=citation,
        label=None,
    )


def read_stage_dd(db: Session, farm: Farm, crop_id: uuid.UUID) -> StageDdOut:
    crop = _require_crop(db, crop_id)
    stages = _stage_rows(db, crop.id)
    farm_rows = {
        row.stage_def_id: row
        for row in db.scalars(
            select(StageDd).where(StageDd.farm_id == farm.id, StageDd.crop_id == crop.id)
        ).all()
    }
    global_rows = {
        row.stage_def_id: row
        for row in db.scalars(
            select(StageDd).where(
                StageDd.farm_id.is_(None),
                StageDd.variety_id.is_(None),
                StageDd.crop_id == crop.id,
            )
        ).all()
    }
    chosen: list[StageDdStageOut] = []
    for stage in stages:
        farm_row = farm_rows.get(stage.id)
        if farm_row is not None:
            chosen.append(_from_row(stage, farm_row))
            continue
        global_row = global_rows.get(stage.id)
        if global_row is not None:
            chosen.append(_from_row(stage, global_row))
            continue
        chosen.append(_empty_stage(stage))
    return StageDdOut(crop_id=crop.id, stages=chosen)


def _gdd_setting(db: Session, farm_id: uuid.UUID, crop_id: uuid.UUID) -> GddSetting | None:
    return db.scalar(
        select(GddSetting).where(GddSetting.farm_id == farm_id, GddSetting.crop_id == crop_id)
    )


def _check_items(
    stages: dict[uuid.UUID, StageDef],
    items: list[StageDdItemIn],
    setting: GddSetting | None,
) -> None:
    fields: dict[str, str] = {}
    seen: set[uuid.UUID] = set()
    for index, item in enumerate(items):
        stage = stages.get(item.stage_def_id)
        if stage is None:
            fields[f"items.{index}.stage_def_id"] = "phenology.stage_not_found"
            continue
        if item.stage_def_id in seen:
            fields[f"items.{index}.stage_def_id"] = "phenology.duplicate_stage"
            continue
        seen.add(item.stage_def_id)
        if item.dd_value is not None and item.dd_value <= 0:
            fields[f"items.{index}.dd_value"] = "phenology.dd_must_be_positive"
        if item.dd_value is not None and setting is not None and item.base_c != setting.base_c:
            fields[f"items.{index}.base_c"] = "phenology.base_mismatch"
    if fields:
        raise AppError("validation_error", 422, fields)


def _same(row: StageDd, item: StageDdItemIn, value: Decimal) -> bool:
    return (
        row.dd_value == value
        and row.base_c == item.base_c
        and row.upper_c == item.upper_c
        and row.method == item.method
        and row.source_kind == StageDdSource.entered
        and row.citation is None
        and row.variety_id is None
    )


def _reason(items: list[StageDdItemIn]) -> str | None:
    notes = [item.note.strip() for item in items if item.note is not None and item.note.strip()]
    if not notes:
        return None
    return "\n".join(notes)


def _next_version(db: Session, farm_id: uuid.UUID, crop_id: uuid.UUID) -> int:
    current = db.scalar(
        select(func.max(RecordVersion.version)).where(
            RecordVersion.farm_id == farm_id,
            RecordVersion.entity_type == _STAGE_DD,
            RecordVersion.entity_id == crop_id,
        )
    )
    return int(current or 0) + 1


def write_stage_dd(db: Session, farm: Farm, user: AppUser, body: StageDdPut) -> StageDdOut:
    crop = _require_crop(db, body.crop_id)
    stages = {row.id: row for row in _stage_rows(db, crop.id)}
    setting = _gdd_setting(db, farm.id, crop.id)
    _check_items(stages, body.items, setting)
    existing = {
        row.stage_def_id: row
        for row in db.scalars(
            select(StageDd).where(StageDd.farm_id == farm.id, StageDd.crop_id == crop.id)
        ).all()
    }
    desired: dict[uuid.UUID, tuple[StageDdItemIn, Decimal]] = {}
    for item in body.items:
        if item.dd_value is None:
            continue
        desired[item.stage_def_id] = (item, item.dd_value)
    changed: list[tuple[int, str]] = []
    for stage_id, row in existing.items():
        stage = stages[stage_id]
        incoming = desired.get(stage_id)
        if incoming is None:
            changed.append((stage.sort, stage.code))
            db.delete(row)
            continue
        item, value = incoming
        if _same(row, item, value):
            continue
        changed.append((stage.sort, stage.code))
        row.dd_value = value
        row.base_c = item.base_c
        row.upper_c = item.upper_c
        row.method = item.method
        row.source_kind = StageDdSource.entered
        row.citation = None
        row.variety_id = None
    for stage_id, (item, value) in desired.items():
        if stage_id in existing:
            continue
        stage = stages[stage_id]
        changed.append((stage.sort, stage.code))
        db.add(
            StageDd(
                crop_id=crop.id,
                variety_id=None,
                stage_def_id=stage.id,
                dd_value=value,
                base_c=item.base_c,
                upper_c=item.upper_c,
                method=item.method,
                source_kind=StageDdSource.entered,
                citation=None,
                farm_id=farm.id,
            )
        )
    db.add(
        RecordVersion(
            farm_id=farm.id,
            entity_type=_STAGE_DD,
            entity_id=crop.id,
            version=_next_version(db, farm.id, crop.id),
            changed_fields=[code for _, code in sorted(changed)],
            reason=_reason(body.items),
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )
    db.flush()
    from app.modules.phenology.service import recompute_crop

    recompute_crop(db, farm.id, crop.id)
    db.commit()
    return read_stage_dd(db, farm, crop.id)


def read_stage_prefs(db: Session, farm: Farm, crop_id: uuid.UUID) -> StagePrefsOut:
    crop = _require_crop(db, crop_id)
    stage_ids = [row.id for row in _stage_rows(db, crop.id)]
    if not stage_ids:
        return StagePrefsOut(items=[])
    rows = db.scalars(
        select(FarmStagePref).where(
            FarmStagePref.farm_id == farm.id,
            FarmStagePref.stage_def_id.in_(stage_ids),
        )
    ).all()
    order = {stage_id: index for index, stage_id in enumerate(stage_ids)}
    chosen = sorted(rows, key=lambda row: order.get(row.stage_def_id, 0))
    return StagePrefsOut(
        items=[
            StagePrefItemOut(
                stage_def_id=row.stage_def_id,
                hidden=row.hidden,
                local_name=row.local_name,
            )
            for row in chosen
        ]
    )


def write_stage_prefs(db: Session, farm: Farm, body: StagePrefsPut) -> StagePrefsOut:
    ids = [item.stage_def_id for item in body.items]
    found: dict[uuid.UUID, StageDef] = {}
    if ids:
        found = {
            row.id: row for row in db.scalars(select(StageDef).where(StageDef.id.in_(ids))).all()
        }
    fields: dict[str, str] = {}
    seen: set[uuid.UUID] = set()
    for index, item in enumerate(body.items):
        if item.stage_def_id not in found:
            fields[f"items.{index}.stage_def_id"] = "phenology.stage_not_found"
            continue
        if item.stage_def_id in seen:
            fields[f"items.{index}.stage_def_id"] = "phenology.duplicate_stage"
            continue
        seen.add(item.stage_def_id)
    if fields:
        raise AppError("validation_error", 422, fields)
    existing: dict[uuid.UUID, FarmStagePref] = {}
    if ids:
        existing = {
            row.stage_def_id: row
            for row in db.scalars(
                select(FarmStagePref).where(
                    FarmStagePref.farm_id == farm.id,
                    FarmStagePref.stage_def_id.in_(ids),
                )
            ).all()
        }
    saved: list[StagePrefItemOut] = []
    for item in body.items:
        local_name = _blank(item.local_name)
        row = existing.get(item.stage_def_id)
        if row is None:
            row = FarmStagePref(
                farm_id=farm.id,
                stage_def_id=item.stage_def_id,
                hidden=item.hidden,
                local_name=local_name,
            )
            db.add(row)
        else:
            row.hidden = item.hidden
            row.local_name = local_name
        saved.append(
            StagePrefItemOut(
                stage_def_id=item.stage_def_id,
                hidden=item.hidden,
                local_name=local_name,
            )
        )
    db.commit()
    return StagePrefsOut(items=saved)
