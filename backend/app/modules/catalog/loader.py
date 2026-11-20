"""Load data/catalog/*.yaml into the catalogue tables. Idempotent."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import NoReturn

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT
from app.core.db import SessionLocal
from app.modules.catalog.models import (
    Crop,
    CropKind,
    CropScale,
    CropScaleCode,
    SoilTextureClass,
    StageDd,
    StageDdSource,
    StageDef,
    TrainingSystem,
    Variety,
    VarietyChill,
)
from app.modules.weather.models import GddMethod

CATALOG_DIR = REPO_ROOT / "data" / "catalog"

_THETA_FIELDS = (
    "theta_fc_min",
    "theta_fc_max",
    "theta_wp_min",
    "theta_wp_max",
    "theta_fc",
    "theta_wp",
)


def _parse_decimal(value: object, label: str) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a decimal string or null")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"{label} must be a decimal string or null") from exc
    if not parsed.is_finite():
        raise ValueError(f"{label} must be a decimal string or null")
    return parsed


def _parse_theta(value: object) -> Decimal | None:
    return _parse_decimal(value, "theta")


def _parse_code(value: object) -> str:
    if isinstance(value, str) and value.strip() != "":
        return value
    raise ValueError("code must be a string")


class _Localized(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fr: str = Field(min_length=1)
    ar: str = Field(min_length=1)
    en: str = Field(min_length=1)


class _CropEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    kind: CropKind
    sort: int
    name: _Localized


class _CropFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crops: list[_CropEntry]


class _VarietyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=1)
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    sort: int


class _VarietyFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    varieties: list[_VarietyEntry]


class _TrainingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=1)
    code: str = Field(min_length=1)
    sort: int
    name: _Localized
    description: _Localized


class _TrainingFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    training_systems: list[_TrainingEntry]


class _SoilEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    sort: int
    name: _Localized
    theta_fc_min: Decimal | None
    theta_fc_max: Decimal | None
    theta_wp_min: Decimal | None
    theta_wp_max: Decimal | None
    theta_fc: Decimal | None
    theta_wp: Decimal | None
    citation: str | None

    @field_validator(*_THETA_FIELDS, mode="before")
    @classmethod
    def theta_strings(cls, value: object) -> Decimal | None:
        return _parse_theta(value)

    @field_validator("citation")
    @classmethod
    def citation_not_blank(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            raise ValueError("citation is empty")
        return value

    def check_theta(self) -> None:
        values = [getattr(self, name) for name in _THETA_FIELDS]
        all_values = all(value is not None for value in values)
        no_values = all(value is None for value in values)
        if all_values and self.citation is not None:
            self._check_ranges()
            return
        if no_values and self.citation is None:
            return
        raise ValueError("theta values and citation must all be set or all be null")

    def _check_ranges(self) -> None:
        fc_min = self.theta_fc_min
        fc_max = self.theta_fc_max
        wp_min = self.theta_wp_min
        wp_max = self.theta_wp_max
        theta_fc = self.theta_fc
        theta_wp = self.theta_wp
        if (
            fc_min is None
            or fc_max is None
            or wp_min is None
            or wp_max is None
            or theta_fc is None
            or theta_wp is None
        ):
            raise ValueError("theta values and citation must all be set or all be null")
        if fc_min > fc_max:
            raise ValueError("theta_fc_min greater than theta_fc_max")
        if wp_min > wp_max:
            raise ValueError("theta_wp_min greater than theta_wp_max")
        if wp_max > fc_max:
            raise ValueError("theta_wp_max greater than theta_fc_max")
        if theta_fc != (fc_min + fc_max) / Decimal(2):
            raise ValueError("theta_fc is not the midpoint")
        if theta_wp != (wp_min + wp_max) / Decimal(2):
            raise ValueError("theta_wp is not the midpoint")


class _SoilFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    soil_textures: list[_SoilEntry]


class _StageEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    sort: int
    name: _Localized
    description: _Localized

    @field_validator("code", mode="before")
    @classmethod
    def code_string(cls, value: object) -> str:
        return _parse_code(value)


class _CropStagesEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=1)
    scale: CropScaleCode
    scale_citation: str = Field(min_length=1)
    stages: list[_StageEntry]

    @field_validator("scale_citation")
    @classmethod
    def citation_not_blank(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("citation is empty")
        return value


class _StagesFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crops: list[_CropStagesEntry]


class _StageDdEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    variety: str | None = None
    dd_value: Decimal
    base_c: Decimal
    upper_c: Decimal | None = None
    method: GddMethod
    source_kind: StageDdSource
    citation: str | None = None

    @field_validator("stage", mode="before")
    @classmethod
    def stage_string(cls, value: object) -> str:
        return _parse_code(value)

    @field_validator("variety", mode="before")
    @classmethod
    def variety_string(cls, value: object) -> str | None:
        if value is None:
            return None
        return _parse_code(value)

    @field_validator("dd_value", "base_c", "upper_c", mode="before")
    @classmethod
    def decimal_strings(cls, value: object) -> Decimal | None:
        return _parse_decimal(value, "value")

    @field_validator("citation")
    @classmethod
    def citation_not_blank(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            raise ValueError("citation is empty")
        return value


class _StageDdFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_dd: list[_StageDdEntry]


class _VarietyChillEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crop: str = Field(min_length=1)
    variety: str = Field(min_length=1)
    chill_h: Decimal | None = None
    chill_portions: Decimal | None = None
    citation: str | None = None

    @field_validator("variety", mode="before")
    @classmethod
    def variety_string(cls, value: object) -> str:
        return _parse_code(value)

    @field_validator("chill_h", "chill_portions", mode="before")
    @classmethod
    def decimal_strings(cls, value: object) -> Decimal | None:
        return _parse_decimal(value, "value")

    @field_validator("citation")
    @classmethod
    def citation_not_blank(cls, value: str | None) -> str | None:
        if value is not None and value.strip() == "":
            raise ValueError("citation is empty")
        return value


class _VarietyChillFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variety_chill: list[_VarietyChillEntry]


@dataclass(frozen=True)
class _Catalog:
    crops: list[_CropEntry]
    varieties: list[_VarietyEntry]
    training_systems: list[_TrainingEntry]
    soil_textures: list[_SoilEntry]
    stage_crops: list[_CropStagesEntry]
    stage_dd: list[_StageDdEntry]
    variety_chill: list[_VarietyChillEntry]


def _fail(path: Path, entry: str, reason: str) -> NoReturn:
    print(f"{path.name}: {entry}: {reason}")
    raise SystemExit(1)


def _entry_from_error(raw: object, loc: tuple[object, ...]) -> str:
    node: object = raw
    entry = "file"
    for part in loc:
        if isinstance(node, dict) and isinstance(part, str) and part in node:
            node = node[part]
            continue
        if isinstance(node, list) and isinstance(part, int) and 0 <= part < len(node):
            node = node[part]
            if isinstance(node, dict):
                code = node.get("code")
                crop = node.get("crop")
                if isinstance(crop, str) and isinstance(code, str):
                    entry = f"{crop}/{code}"
                elif isinstance(code, str):
                    entry = code
                else:
                    entry = str(part)
            else:
                entry = str(part)
            continue
        break
    return entry


def _load_raw(path: Path) -> object:
    if not path.is_file():
        _fail(path, "file", "not found")
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"{path.name}: file: {exc}")
        raise SystemExit(1) from exc


def _load_model[T: BaseModel](path: Path, model: type[T]) -> T:
    raw = _load_raw(path)
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        for err in exc.errors():
            loc = tuple(err["loc"])
            print(f"{path.name}: {_entry_from_error(raw, loc)}: {err['msg']}")
        raise SystemExit(1) from exc


def _ensure_unique(path: Path, labels: Sequence[str]) -> None:
    seen: set[str] = set()
    for label in labels:
        if label in seen:
            _fail(path, label, "duplicate key")
        seen.add(label)


def _stage_label(entry: _StageDdEntry) -> str:
    return f"{entry.crop}/{entry.stage}"


def _require_citation(path: Path, label: str, citation: str | None) -> None:
    if citation is None or citation.strip() == "":
        _fail(path, label, "citation is required")


def _read_catalog(directory: Path) -> _Catalog:
    crops_path = directory / "crops.yaml"
    varieties_path = directory / "varieties.yaml"
    training_path = directory / "training_systems.yaml"
    soil_path = directory / "soil_textures.yaml"
    stages_path = directory / "stages.yaml"
    stage_dd_path = directory / "stage_dd.yaml"
    chill_path = directory / "variety_chill.yaml"
    crops = _load_model(crops_path, _CropFile)
    varieties = _load_model(varieties_path, _VarietyFile)
    training = _load_model(training_path, _TrainingFile)
    soil = _load_model(soil_path, _SoilFile)
    stages = _load_model(stages_path, _StagesFile)
    stage_dd = _load_model(stage_dd_path, _StageDdFile)
    chill = _load_model(chill_path, _VarietyChillFile)
    for entry in soil.soil_textures:
        try:
            entry.check_theta()
        except ValueError as exc:
            _fail(soil_path, entry.code, str(exc))
    _ensure_unique(crops_path, [entry.code for entry in crops.crops])
    _ensure_unique(
        varieties_path,
        [f"{entry.crop}/{entry.code}" for entry in varieties.varieties],
    )
    _ensure_unique(
        training_path,
        [f"{entry.crop}/{entry.code}" for entry in training.training_systems],
    )
    _ensure_unique(soil_path, [entry.code for entry in soil.soil_textures])
    _ensure_unique(stages_path, [entry.crop for entry in stages.crops])
    _ensure_unique(
        stages_path,
        [f"{entry.crop}/{stage.code}" for entry in stages.crops for stage in entry.stages],
    )
    _ensure_unique(
        stage_dd_path,
        [f"{entry.crop}/{entry.variety or '-'}/{entry.stage}" for entry in stage_dd.stage_dd],
    )
    _ensure_unique(
        chill_path,
        [f"{entry.crop}/{entry.variety}" for entry in chill.variety_chill],
    )
    crop_codes = {entry.code for entry in crops.crops}
    for entry in varieties.varieties:
        if entry.crop not in crop_codes:
            _fail(varieties_path, f"{entry.crop}/{entry.code}", f"unknown crop '{entry.crop}'")
    for entry in training.training_systems:
        if entry.crop not in crop_codes:
            _fail(training_path, f"{entry.crop}/{entry.code}", f"unknown crop '{entry.crop}'")
    stage_codes: dict[str, set[str]] = {}
    for entry in stages.crops:
        if entry.crop not in crop_codes:
            _fail(stages_path, entry.crop, f"unknown crop '{entry.crop}'")
        if not entry.stages:
            _fail(stages_path, entry.crop, "crop has no stages")
        stage_codes[entry.crop] = {stage.code for stage in entry.stages}
    missing_crops = sorted(crop_codes - set(stage_codes))
    if missing_crops:
        _fail(stages_path, missing_crops[0], "crop has no stages")
    variety_codes: dict[str, set[str]] = {}
    for entry in varieties.varieties:
        variety_codes.setdefault(entry.crop, set()).add(entry.code)
    for entry in stage_dd.stage_dd:
        label = _stage_label(entry)
        _require_citation(stage_dd_path, label, entry.citation)
        if entry.crop not in crop_codes:
            _fail(stage_dd_path, label, f"unknown crop '{entry.crop}'")
        if entry.stage not in stage_codes.get(entry.crop, set()):
            _fail(stage_dd_path, label, f"unknown stage '{entry.stage}'")
        if entry.variety is not None and entry.variety not in variety_codes.get(entry.crop, set()):
            _fail(stage_dd_path, label, f"unknown variety '{entry.variety}'")
        if entry.source_kind == StageDdSource.entered:
            _fail(stage_dd_path, label, "catalogue source cannot be entered")
        if entry.dd_value <= 0:
            _fail(stage_dd_path, label, "dd_value must be positive")
    for entry in chill.variety_chill:
        label = f"{entry.crop}/{entry.variety}"
        _require_citation(chill_path, label, entry.citation)
        if entry.crop not in crop_codes:
            _fail(chill_path, label, f"unknown crop '{entry.crop}'")
        if entry.variety not in variety_codes.get(entry.crop, set()):
            _fail(chill_path, label, f"unknown variety '{entry.variety}'")
    return _Catalog(
        crops=crops.crops,
        varieties=varieties.varieties,
        training_systems=training.training_systems,
        soil_textures=soil.soil_textures,
        stage_crops=stages.crops,
        stage_dd=stage_dd.stage_dd,
        variety_chill=chill.variety_chill,
    )


def _apply(row: object, values: dict[str, object]) -> None:
    changed = False
    for key, value in values.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed and hasattr(row, "updated_at"):
        row.updated_at = datetime.now(UTC)


def _upsert_crops(db: Session, entries: list[_CropEntry]) -> dict[str, Crop]:
    existing = {row.code: row for row in db.scalars(select(Crop)).all()}
    for entry in entries:
        values: dict[str, object] = {
            "kind": entry.kind,
            "sort": entry.sort,
            "name_fr": entry.name.fr,
            "name_ar": entry.name.ar,
            "name_en": entry.name.en,
        }
        row = existing.get(entry.code)
        if row is None:
            row = Crop(
                code=entry.code,
                kind=entry.kind,
                sort=entry.sort,
                name_fr=entry.name.fr,
                name_ar=entry.name.ar,
                name_en=entry.name.en,
            )
            db.add(row)
            existing[entry.code] = row
        else:
            _apply(row, values)
    db.flush()
    return existing


def _upsert_varieties(db: Session, crops: dict[str, Crop], entries: list[_VarietyEntry]) -> None:
    existing = {(row.crop_id, row.code): row for row in db.scalars(select(Variety)).all()}
    for entry in entries:
        crop = crops[entry.crop]
        row = existing.get((crop.id, entry.code))
        if row is None:
            db.add(Variety(crop_id=crop.id, code=entry.code, name=entry.name, sort=entry.sort))
            continue
        _apply(row, {"name": entry.name, "sort": entry.sort})


def _upsert_training(db: Session, crops: dict[str, Crop], entries: list[_TrainingEntry]) -> None:
    existing = {(row.crop_id, row.code): row for row in db.scalars(select(TrainingSystem)).all()}
    for entry in entries:
        crop = crops[entry.crop]
        values: dict[str, object] = {
            "sort": entry.sort,
            "name_fr": entry.name.fr,
            "name_ar": entry.name.ar,
            "name_en": entry.name.en,
            "description_fr": entry.description.fr,
            "description_ar": entry.description.ar,
            "description_en": entry.description.en,
        }
        row = existing.get((crop.id, entry.code))
        if row is None:
            db.add(
                TrainingSystem(
                    crop_id=crop.id,
                    code=entry.code,
                    sort=entry.sort,
                    name_fr=entry.name.fr,
                    name_ar=entry.name.ar,
                    name_en=entry.name.en,
                    description_fr=entry.description.fr,
                    description_ar=entry.description.ar,
                    description_en=entry.description.en,
                )
            )
            continue
        _apply(row, values)


def _upsert_soil(db: Session, entries: list[_SoilEntry]) -> None:
    existing = {row.code: row for row in db.scalars(select(SoilTextureClass)).all()}
    for entry in entries:
        values: dict[str, object] = {
            "sort": entry.sort,
            "name_fr": entry.name.fr,
            "name_ar": entry.name.ar,
            "name_en": entry.name.en,
            "theta_fc_min": entry.theta_fc_min,
            "theta_fc_max": entry.theta_fc_max,
            "theta_wp_min": entry.theta_wp_min,
            "theta_wp_max": entry.theta_wp_max,
            "theta_fc": entry.theta_fc,
            "theta_wp": entry.theta_wp,
            "citation": entry.citation,
        }
        row = existing.get(entry.code)
        if row is None:
            db.add(
                SoilTextureClass(
                    code=entry.code,
                    sort=entry.sort,
                    name_fr=entry.name.fr,
                    name_ar=entry.name.ar,
                    name_en=entry.name.en,
                    theta_fc_min=entry.theta_fc_min,
                    theta_fc_max=entry.theta_fc_max,
                    theta_wp_min=entry.theta_wp_min,
                    theta_wp_max=entry.theta_wp_max,
                    theta_fc=entry.theta_fc,
                    theta_wp=entry.theta_wp,
                    citation=entry.citation,
                )
            )
            continue
        _apply(row, values)


def _upsert_scales(db: Session, crops: dict[str, Crop], entries: list[_CropStagesEntry]) -> None:
    existing = {row.crop_id: row for row in db.scalars(select(CropScale)).all()}
    for entry in entries:
        crop = crops[entry.crop]
        values: dict[str, object] = {"scale": entry.scale, "citation": entry.scale_citation}
        row = existing.get(crop.id)
        if row is None:
            db.add(CropScale(crop_id=crop.id, scale=entry.scale, citation=entry.scale_citation))
            continue
        _apply(row, values)


def _upsert_stages(db: Session, crops: dict[str, Crop], entries: list[_CropStagesEntry]) -> None:
    existing = {(row.crop_id, row.code): row for row in db.scalars(select(StageDef)).all()}
    for entry in entries:
        crop = crops[entry.crop]
        for stage in entry.stages:
            values: dict[str, object] = {
                "sort": stage.sort,
                "name_fr": stage.name.fr,
                "name_ar": stage.name.ar,
                "name_en": stage.name.en,
                "description_fr": stage.description.fr,
                "description_ar": stage.description.ar,
                "description_en": stage.description.en,
            }
            row = existing.get((crop.id, stage.code))
            if row is None:
                db.add(
                    StageDef(
                        crop_id=crop.id,
                        code=stage.code,
                        sort=stage.sort,
                        name_fr=stage.name.fr,
                        name_ar=stage.name.ar,
                        name_en=stage.name.en,
                        description_fr=stage.description.fr,
                        description_ar=stage.description.ar,
                        description_en=stage.description.en,
                    )
                )
                continue
            _apply(row, values)


def _upsert_stage_dd(db: Session, crops: dict[str, Crop], entries: list[_StageDdEntry]) -> None:
    varieties = {(row.crop_id, row.code): row for row in db.scalars(select(Variety)).all()}
    stages = {(row.crop_id, row.code): row for row in db.scalars(select(StageDef)).all()}
    existing = {
        (row.stage_def_id, row.variety_id): row
        for row in db.scalars(select(StageDd).where(StageDd.farm_id.is_(None))).all()
    }
    for entry in entries:
        crop = crops[entry.crop]
        stage = stages[(crop.id, entry.stage)]
        variety_id = None
        if entry.variety is not None:
            variety_id = varieties[(crop.id, entry.variety)].id
        values: dict[str, object] = {
            "crop_id": crop.id,
            "dd_value": entry.dd_value,
            "base_c": entry.base_c,
            "upper_c": entry.upper_c,
            "method": entry.method,
            "source_kind": entry.source_kind,
            "citation": entry.citation,
        }
        row = existing.get((stage.id, variety_id))
        if row is None:
            db.add(
                StageDd(
                    crop_id=crop.id,
                    variety_id=variety_id,
                    stage_def_id=stage.id,
                    dd_value=entry.dd_value,
                    base_c=entry.base_c,
                    upper_c=entry.upper_c,
                    method=entry.method,
                    source_kind=entry.source_kind,
                    citation=entry.citation,
                    farm_id=None,
                )
            )
            continue
        _apply(row, values)


def _upsert_variety_chill(
    db: Session,
    crops: dict[str, Crop],
    entries: list[_VarietyChillEntry],
) -> None:
    varieties = {(row.crop_id, row.code): row for row in db.scalars(select(Variety)).all()}
    existing = {row.variety_id: row for row in db.scalars(select(VarietyChill)).all()}
    for entry in entries:
        crop = crops[entry.crop]
        variety = varieties[(crop.id, entry.variety)]
        citation = entry.citation
        if citation is None or citation.strip() == "":
            raise RuntimeError("variety chill citation missing after validation")
        values: dict[str, object] = {
            "chill_h": entry.chill_h,
            "chill_portions": entry.chill_portions,
            "citation": citation,
        }
        row = existing.get(variety.id)
        if row is None:
            db.add(
                VarietyChill(
                    variety_id=variety.id,
                    chill_h=entry.chill_h,
                    chill_portions=entry.chill_portions,
                    citation=citation,
                )
            )
            continue
        _apply(row, values)


def _warn(label: str, missing: list[str]) -> None:
    if missing:
        print(f"warning: {label} missing from YAML: {', '.join(missing)}")


def _warn_missing(db: Session, catalog: _Catalog) -> None:
    crop_codes = {entry.code for entry in catalog.crops}
    _warn(
        "crops",
        [
            row.code
            for row in db.scalars(select(Crop).order_by(Crop.code))
            if row.code not in crop_codes
        ],
    )
    variety_keys = {(entry.crop, entry.code) for entry in catalog.varieties}
    missing_varieties: list[str] = []
    variety_rows = db.execute(
        select(Crop.code, Variety.code)
        .join(Variety, Variety.crop_id == Crop.id)
        .order_by(Crop.code, Variety.code)
    )
    for crop_code, variety_code in variety_rows:
        if (crop_code, variety_code) not in variety_keys:
            missing_varieties.append(f"{crop_code}/{variety_code}")
    _warn("varieties", missing_varieties)
    training_keys = {(entry.crop, entry.code) for entry in catalog.training_systems}
    missing_training: list[str] = []
    training_rows = db.execute(
        select(Crop.code, TrainingSystem.code)
        .join(TrainingSystem, TrainingSystem.crop_id == Crop.id)
        .order_by(Crop.code, TrainingSystem.code)
    )
    for crop_code, training_code in training_rows:
        if (crop_code, training_code) not in training_keys:
            missing_training.append(f"{crop_code}/{training_code}")
    _warn("training systems", missing_training)
    soil_codes = {entry.code for entry in catalog.soil_textures}
    _warn(
        "soil classes",
        [
            row.code
            for row in db.scalars(select(SoilTextureClass).order_by(SoilTextureClass.code))
            if row.code not in soil_codes
        ],
    )
    scale_crops = {entry.crop for entry in catalog.stage_crops}
    missing_scales: list[str] = []
    scale_rows = db.execute(
        select(Crop.code).join(CropScale, CropScale.crop_id == Crop.id).order_by(Crop.code)
    )
    for (crop_code,) in scale_rows:
        if crop_code not in scale_crops:
            missing_scales.append(crop_code)
    _warn("crop scales", missing_scales)
    stage_keys = {
        (entry.crop, stage.code) for entry in catalog.stage_crops for stage in entry.stages
    }
    missing_stages: list[str] = []
    stage_rows = db.execute(
        select(Crop.code, StageDef.code)
        .join(StageDef, StageDef.crop_id == Crop.id)
        .order_by(Crop.code, StageDef.code)
    )
    for crop_code, stage_code in stage_rows:
        if (crop_code, stage_code) not in stage_keys:
            missing_stages.append(f"{crop_code}/{stage_code}")
    _warn("stages", missing_stages)
    stage_dd_keys = {(entry.crop, entry.variety, entry.stage) for entry in catalog.stage_dd}
    missing_stage_dd: list[str] = []
    stage_dd_rows = db.execute(
        select(Crop.code, Variety.code, StageDef.code)
        .select_from(StageDd)
        .join(Crop, Crop.id == StageDd.crop_id)
        .join(StageDef, StageDef.id == StageDd.stage_def_id)
        .join(Variety, Variety.id == StageDd.variety_id, isouter=True)
        .where(StageDd.farm_id.is_(None))
        .order_by(Crop.code, StageDef.code)
    )
    for crop_code, variety_code, stage_code in stage_dd_rows:
        if (crop_code, variety_code, stage_code) not in stage_dd_keys:
            variety_label = variety_code if isinstance(variety_code, str) else "-"
            missing_stage_dd.append(f"{crop_code}/{variety_label}/{stage_code}")
    _warn("stage dd", missing_stage_dd)
    chill_keys = {(entry.crop, entry.variety) for entry in catalog.variety_chill}
    missing_chill: list[str] = []
    chill_rows = db.execute(
        select(Crop.code, Variety.code)
        .join(Variety, Variety.crop_id == Crop.id)
        .join(VarietyChill, VarietyChill.variety_id == Variety.id)
        .order_by(Crop.code, Variety.code)
    )
    for crop_code, variety_code in chill_rows:
        if (crop_code, variety_code) not in chill_keys:
            missing_chill.append(f"{crop_code}/{variety_code}")
    _warn("variety chill", missing_chill)


def _summary(catalog: _Catalog) -> str:
    stage_count = sum(len(entry.stages) for entry in catalog.stage_crops)
    return (
        "catalog ok: "
        f"{len(catalog.crops)} crops, "
        f"{len(catalog.varieties)} varieties, "
        f"{len(catalog.training_systems)} training systems, "
        f"{len(catalog.soil_textures)} soil classes, "
        f"{stage_count} stages, "
        f"{len(catalog.stage_dd)} stage dd, "
        f"{len(catalog.variety_chill)} variety chill"
    )


def load_catalog(catalog_dir: Path | None = None) -> None:
    catalog = _read_catalog(catalog_dir or CATALOG_DIR)
    db = SessionLocal()
    try:
        crops = _upsert_crops(db, catalog.crops)
        _upsert_varieties(db, crops, catalog.varieties)
        _upsert_training(db, crops, catalog.training_systems)
        _upsert_soil(db, catalog.soil_textures)
        _upsert_scales(db, crops, catalog.stage_crops)
        _upsert_stages(db, crops, catalog.stage_crops)
        db.flush()
        _upsert_stage_dd(db, crops, catalog.stage_dd)
        _upsert_variety_chill(db, crops, catalog.variety_chill)
        _warn_missing(db, catalog)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(_summary(catalog))


def main() -> None:
    load_catalog()


if __name__ == "__main__":
    main()
