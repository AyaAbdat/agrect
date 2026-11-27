from __future__ import annotations

import uuid
from datetime import date as Date
from decimal import Decimal

from app.modules.operations.models import OperationType
from app.modules.operations.schemas import ApiModel


class TimelineBlockOut(ApiModel):
    id: uuid.UUID
    name: str


class TimelineCropOut(ApiModel):
    code: str
    names: dict[str, str]


class TimelineStageOut(ApiModel):
    date: Date
    code: str
    names: dict[str, str]


class TimelineHarvestOut(ApiModel):
    date: Date
    pass_no: int
    kg: Decimal


class TimelineOperationOut(ApiModel):
    date: Date
    type: OperationType
    products: list[str]


class TimelineIrrigationWeekOut(ApiModel):
    week_start: Date
    count: int


class TimelineRowOut(ApiModel):
    block: TimelineBlockOut
    crop: TimelineCropOut | None
    season_start: Date | None
    first_harvest_date: Date | None
    stages: list[TimelineStageOut]
    harvest: list[TimelineHarvestOut]
    operations: list[TimelineOperationOut]
    irrigation_weeks: list[TimelineIrrigationWeekOut]


class TimelineOut(ApiModel):
    date_from: Date
    date_to: Date
    blocks: list[TimelineRowOut]
