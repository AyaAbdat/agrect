import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.modules.catalog.models import CropKind


class LocalizedName(BaseModel):
    fr: str
    ar: str
    en: str


class CropOut(BaseModel):
    id: uuid.UUID
    code: str
    kind: CropKind
    name: LocalizedName


class VarietyOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class TrainingSystemOut(BaseModel):
    id: uuid.UUID
    code: str
    name: LocalizedName
    description: LocalizedName


class SoilTextureOut(BaseModel):
    id: uuid.UUID
    code: str
    name: LocalizedName
    theta_fc_min: str | None
    theta_fc_max: str | None
    theta_wp_min: str | None
    theta_wp_max: str | None
    theta_fc: str | None
    theta_wp: str | None
    citation: str | None
    source: Literal["entered"] | None


def format_theta(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.001")), "f")
