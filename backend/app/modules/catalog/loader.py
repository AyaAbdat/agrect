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
from app.modules.catalog.models import Crop, CropKind, SoilTextureClass, TrainingSystem, Variety

CATALOG_DIR = REPO_ROOT / "data" / "catalog"

_THETA_FIELDS = (
    "theta_fc_min",
    "theta_fc_max",
    "theta_wp_min",
    "theta_wp_max",
    "theta_fc",
    "theta_wp",
)


def _parse_theta(value: object) -> Decimal | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("theta must be a decimal string or null")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("theta must be a decimal string or null") from exc
    if not parsed.is_finite():
        raise ValueError("theta must be a decimal string or null")
    return parsed


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


@dataclass(frozen=True)
class _Catalog:
    crops: list[_CropEntry]
    varieties: list[_VarietyEntry]
    training_systems: list[_TrainingEntry]
    soil_textures: list[_SoilEntry]


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


def _read_catalog(directory: Path) -> _Catalog:
    crops_path = directory / "crops.yaml"
    varieties_path = directory / "varieties.yaml"
    training_path = directory / "training_systems.yaml"
    soil_path = directory / "soil_textures.yaml"
    crops = _load_model(crops_path, _CropFile)
    varieties = _load_model(varieties_path, _VarietyFile)
    training = _load_model(training_path, _TrainingFile)
    soil = _load_model(soil_path, _SoilFile)
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
    crop_codes = {entry.code for entry in crops.crops}
    for entry in varieties.varieties:
        if entry.crop not in crop_codes:
            _fail(varieties_path, f"{entry.crop}/{entry.code}", f"unknown crop '{entry.crop}'")
    for entry in training.training_systems:
        if entry.crop not in crop_codes:
            _fail(training_path, f"{entry.crop}/{entry.code}", f"unknown crop '{entry.crop}'")
    return _Catalog(
        crops=crops.crops,
        varieties=varieties.varieties,
        training_systems=training.training_systems,
        soil_textures=soil.soil_textures,
    )


def _apply(
    row: Crop | Variety | TrainingSystem | SoilTextureClass,
    values: dict[str, object],
) -> None:
    changed = False
    for key, value in values.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changed = True
    if changed:
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


def _summary(catalog: _Catalog) -> str:
    return (
        "catalog ok: "
        f"{len(catalog.crops)} crops, "
        f"{len(catalog.varieties)} varieties, "
        f"{len(catalog.training_systems)} training systems, "
        f"{len(catalog.soil_textures)} soil classes"
    )


def load_catalog(catalog_dir: Path | None = None) -> None:
    catalog = _read_catalog(catalog_dir or CATALOG_DIR)
    db = SessionLocal()
    try:
        crops = _upsert_crops(db, catalog.crops)
        _upsert_varieties(db, crops, catalog.varieties)
        _upsert_training(db, crops, catalog.training_systems)
        _upsert_soil(db, catalog.soil_textures)
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
