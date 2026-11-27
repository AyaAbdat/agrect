from __future__ import annotations

import uuid
from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.labour.models import WorkerKind, WorkerRole
from app.modules.operations.models import OperationType
from app.modules.operations.schemas import ApiModel, OptionalDecimal


class WorkerIn(BaseModel):
    name: str
    role: WorkerRole
    kind: WorkerKind
    phone: str | None = None
    active: bool = True


class WorkerPatch(BaseModel):
    name: str | None = None
    role: WorkerRole | None = None
    kind: WorkerKind | None = None
    phone: str | None = None
    active: bool | None = None
    reason: str | None = None


class WorkerOut(ApiModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    name: str
    role: WorkerRole
    kind: WorkerKind
    phone: str | None
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class WorkerListOut(ApiModel):
    workers: list[WorkerOut]


class AttendanceItemIn(BaseModel):
    worker_id: uuid.UUID
    present: bool
    hours: OptionalDecimal = None
    note: str | None = None


class AttendancePut(BaseModel):
    date: Date
    items: list[AttendanceItemIn] = Field(default_factory=list)


class AttendanceItemOut(ApiModel):
    worker_id: uuid.UUID
    worker_name: str
    present: bool
    hours: Decimal | None
    note: str | None
    source: Literal["entered"] = "entered"


class AttendanceDayOut(ApiModel):
    date: Date
    items: list[AttendanceItemOut]


class AttendanceSummaryRowOut(ApiModel):
    worker_id: uuid.UUID
    worker_name: str
    days_present: int
    hours: Decimal
    source: Literal["calculated"] = "calculated"


class AttendanceSummaryOut(ApiModel):
    date_from: Date
    date_to: Date
    workers: list[AttendanceSummaryRowOut]


class NormCropOut(ApiModel):
    id: uuid.UUID
    code: str
    name: dict[str, str]


class LabourNormOut(ApiModel):
    operation_type: OperationType
    crop: NormCropOut | None
    total_hours: Decimal
    total_area_ha: Decimal
    h_per_ha: Decimal | None
    operations_count: int
    source: Literal["calculated"] = "calculated"


class LabourNormListOut(ApiModel):
    season: int
    rows: list[LabourNormOut]
