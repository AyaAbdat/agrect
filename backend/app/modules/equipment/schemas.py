from __future__ import annotations

import uuid
from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.equipment.models import MachineStatus, MachineType
from app.modules.operations.schemas import ApiModel, OptionalDecimal


class MachineIn(BaseModel):
    type: MachineType
    name: str
    status: MachineStatus = MachineStatus.ok
    engine_hours_reading: OptionalDecimal = None
    reading_date: Date | None = None


class MachinePatch(BaseModel):
    type: MachineType | None = None
    name: str | None = None
    status: MachineStatus | None = None
    engine_hours_reading: OptionalDecimal = None
    reading_date: Date | None = None
    reason: str | None = None


class MachineOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    type: MachineType
    name: str
    status: MachineStatus
    engine_hours_reading: Decimal | None
    reading_date: Date | None
    version: int
    created_at: datetime
    updated_at: datetime


class MachineListItemOut(MachineOut):
    """A machine row with what the list shows (additive to MachineOut)."""

    current_engine_hours: Decimal | None
    current_engine_hours_source: Literal["calculated"] | None
    maintenance: list[MaintenanceOut]


class MachineListOut(ApiModel):
    machines: list[MachineListItemOut]


class MaintenanceIn(BaseModel):
    task: str
    interval_h: OptionalDecimal = None
    interval_days: int | None = Field(default=None, gt=0)
    last_done_date: Date | None = None
    last_done_h: OptionalDecimal = None


class MaintenancePatch(BaseModel):
    task: str | None = None
    interval_h: OptionalDecimal = None
    interval_days: int | None = Field(default=None, gt=0)
    last_done_date: Date | None = None
    last_done_h: OptionalDecimal = None
    reason: str | None = None


class MaintenanceDoneIn(BaseModel):
    date: Date
    engine_hours: OptionalDecimal = None


class MaintenanceDueOut(ApiModel):
    due_by_hours: bool
    due_by_date: bool
    next_due_h: Decimal | None
    next_due_date: Date | None
    overdue: bool
    source: Literal["calculated"] = "calculated"


class MachineBriefOut(ApiModel):
    id: uuid.UUID
    name: str


class MaintenanceOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    machine: MachineBriefOut
    task: str
    interval_h: Decimal | None
    interval_days: int | None
    last_done_date: Date | None
    last_done_h: Decimal | None
    due: MaintenanceDueOut
    version: int
    created_at: datetime
    updated_at: datetime


class MaintenanceListOut(ApiModel):
    items: list[MaintenanceOut]


class MachineSeasonUseOut(ApiModel):
    season: int
    uses_count: int
    hours: Decimal
    fuel_l: Decimal
    area_ha: Decimal
    avg_work_rate_ha_h: Decimal | None
    source: Literal["calculated"] = "calculated"


class MachineDetailOut(MachineOut):
    current_engine_hours: Decimal | None
    current_engine_hours_source: Literal["calculated"] | None
    uses_this_season: MachineSeasonUseOut
    maintenance: list[MaintenanceOut]


MachineListItemOut.model_rebuild()
MachineListOut.model_rebuild()
