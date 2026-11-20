import enum
import uuid
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_serializer

from app.modules.catalog.models import CropKind, CropScaleCode
from app.modules.weather.models import GddMethod


def _parse_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, bool) or not isinstance(value, int | str | float):
        raise ValueError("invalid decimal")
    else:
        try:
            parsed = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("invalid decimal") from exc
    if not parsed.is_finite():
        raise ValueError("invalid decimal")
    return parsed


def _parse_optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return _parse_decimal(value)


DecimalIn = Annotated[Decimal, BeforeValidator(_parse_decimal)]
OptionalDecimalIn = Annotated[Decimal | None, BeforeValidator(_parse_optional_decimal)]


class JsonModel(BaseModel):
    @field_serializer("*", mode="plain")
    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, enum.Enum):
            return value.value
        return value


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


class StageOut(BaseModel):
    id: uuid.UUID
    code: str
    sort: int
    name: LocalizedName
    description: LocalizedName


class CropStagesOut(BaseModel):
    scale: CropScaleCode
    scale_citation: str
    stages: list[StageOut]


class StageDdStageOut(JsonModel):
    stage_def_id: uuid.UUID
    code: str
    sort: int
    name: LocalizedName
    dd_value: Decimal | None
    base_c: Decimal | None
    upper_c: Decimal | None
    method: GddMethod | None
    source: Literal["entered", "literature", "farm_seasons"] | None
    citation: str | None
    label: Literal["not_enough_data"] | None


class StageDdOut(BaseModel):
    crop_id: uuid.UUID
    stages: list[StageDdStageOut]


class StageDdItemIn(BaseModel):
    stage_def_id: uuid.UUID
    dd_value: OptionalDecimalIn
    base_c: DecimalIn
    upper_c: OptionalDecimalIn = None
    method: GddMethod
    note: str | None = None


class StageDdPut(BaseModel):
    crop_id: uuid.UUID
    items: list[StageDdItemIn]


class StagePrefItemIn(BaseModel):
    stage_def_id: uuid.UUID
    hidden: bool
    local_name: str | None = Field(default=None, max_length=255)


class StagePrefsPut(BaseModel):
    items: list[StagePrefItemIn]


class StagePrefItemOut(BaseModel):
    stage_def_id: uuid.UUID
    hidden: bool
    local_name: str | None


class StagePrefsOut(BaseModel):
    items: list[StagePrefItemOut]
