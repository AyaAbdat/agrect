import enum
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, field_serializer

from app.modules.catalog.schemas import LocalizedName
from app.modules.phenology.models import PredictionLabel, SeasonStatus
from app.modules.weather.models import GddMethod

HistoryStatus = Literal["ready", "loading", "empty"]
DdSource = Literal["entered", "literature"]


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


OptionalDecimalIn = Annotated[Decimal | None, BeforeValidator(_parse_optional_decimal)]


class JsonModel(BaseModel):
    @field_serializer("*", mode="plain")
    def _serialize_value(self, value: object) -> object:
        if isinstance(value, Decimal):
            return format(value, "f")
        if isinstance(value, enum.Enum):
            return value.value
        return value


class StageBrief(JsonModel):
    id: uuid.UUID
    code: str
    name: LocalizedName


class SeasonPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_date: date | None = None
    start_stage_def_id: uuid.UUID | None = None


class SeasonOut(JsonModel):
    id: uuid.UUID
    block_id: uuid.UUID
    year: int
    start_date: date | None
    start_stage_def_id: uuid.UUID | None
    start_stage: StageBrief | None = None
    start_observed: bool
    status: SeasonStatus


class ObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_def_id: uuid.UUID
    observed_on: date
    share_pct: OptionalDecimalIn = None


class ObservationOut(JsonModel):
    id: uuid.UUID
    block_season_id: uuid.UUID
    stage_def_id: uuid.UUID
    observed_on: date
    share_pct: Decimal | None


class SettingOut(JsonModel):
    base_c: Decimal
    upper_c: Decimal | None
    method: GddMethod


class TodayOut(JsonModel):
    dd_counted: Decimal | None
    current_stage: StageBrief | None
    next_stage: StageBrief | None


class StageRowOut(JsonModel):
    stage: StageBrief
    label: PredictionLabel
    date: date | None
    earliest: date | None
    latest: date | None
    dd_needed: Decimal | None
    dd_counted: Decimal | None
    dd_source: DdSource | None
    citation: str | None
    reason: str | None


class HistoryOut(JsonModel):
    years_count: int
    status: HistoryStatus


class ObservationItemOut(JsonModel):
    id: uuid.UUID
    stage_def_id: uuid.UUID
    observed_on: date
    share_pct: Decimal | None


class BlockStagesOut(JsonModel):
    season: SeasonOut
    setting: SettingOut | None
    history_status: HistoryStatus
    history: HistoryOut
    today: TodayOut
    stages: list[StageRowOut]
    observations: list[ObservationItemOut]


class SummaryNextOut(JsonModel):
    stage: StageBrief
    date: date


class SummaryBlockOut(JsonModel):
    block_id: uuid.UUID
    name: str
    season_id: uuid.UUID | None
    year: int
    current_stage: StageBrief | None
    next_stage: SummaryNextOut | None


class StageSummaryOut(JsonModel):
    crop_id: uuid.UUID
    blocks: list[SummaryBlockOut]
