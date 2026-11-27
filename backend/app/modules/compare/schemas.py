from __future__ import annotations

import enum
import uuid
from datetime import date as Date
from decimal import Decimal
from typing import Literal

from app.modules.operations.schemas import ApiModel

Source = Literal["measured", "estimated", "calculated", "entered"]


class CompareMetric(enum.StrEnum):
    water_left = "water_left"
    water_applied = "water_applied"
    crop_water_use = "crop_water_use"
    degree_days = "degree_days"
    stage = "stage"
    pest_count = "pest_count"


class CompareBlockOut(ApiModel):
    id: uuid.UUID
    name: str


class CompareRowOut(ApiModel):
    block: CompareBlockOut
    value: Decimal | str | None
    value_name: dict[str, str] | None = None
    unit: str | None
    mean_7d: Decimal | None
    source: Source | None


class CompareFlagOut(ApiModel):
    block_ids: list[uuid.UUID]
    metric: Literal["water_left"] = "water_left"
    message_code: Literal["compare.drift_same_setting"] = "compare.drift_same_setting"


class CompareOut(ApiModel):
    metric: CompareMetric
    date: Date
    available: bool
    unavailable_code: Literal["compare.metric_unavailable"] | None = None
    rows: list[CompareRowOut]
    flags: list[CompareFlagOut]
