"""Labour: workers, daily attendance, hours per operation, labour norms (h/ha).

Source: AGRECT system design — Labour.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import any_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop
from app.modules.farms.models import Farm
from app.modules.labour import calc
from app.modules.labour.models import Attendance, LabourLog, Worker
from app.modules.labour.schemas import (
    AttendanceDayOut,
    AttendanceItemOut,
    AttendancePut,
    AttendanceSummaryOut,
    AttendanceSummaryRowOut,
    LabourNormListOut,
    LabourNormOut,
    NormCropOut,
    WorkerIn,
    WorkerListOut,
    WorkerOut,
    WorkerPatch,
)
from app.modules.operations.models import Operation, OperationType
from app.modules.operations.schemas import (
    OperationLabourIn,
    OperationLabourOut,
    OperationLabourWorkerOut,
    OperationWarningOut,
)
from app.modules.registry.models import Block, RecordVersion

_ENTITY_WORKER = "worker"
_WORKER_FIELDS = ("name", "role", "kind", "phone", "active")


def _require_if_match(version: int, if_match: str | None) -> None:
    if if_match is None or if_match.strip() == "":
        raise AppError("conflict.version_required", 428)
    token = if_match.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        token = token[1:-1]
    try:
        presented = int(token)
    except ValueError:
        raise AppError("conflict.version", 409) from None
    if presented != version:
        raise AppError("conflict.version", 409)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _add_history(
    db: Session,
    *,
    row: Worker,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=row.farm_id,
            entity_type=_ENTITY_WORKER,
            entity_id=row.id,
            version=row.version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


# --- workers ---------------------------------------------------------------


def _worker_out(row: Worker) -> WorkerOut:
    return WorkerOut(
        id=row.id,
        farm_id=row.farm_id,
        name=row.name,
        role=row.role,
        kind=row.kind,
        phone=row.phone,
        active=row.active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _worker_or_404(db: Session, user: AppUser, worker_id: uuid.UUID) -> Worker:
    row = db.get(Worker, worker_id)
    if row is None:
        raise AppError("worker.not_found", 404)
    farm = db.get(Farm, row.farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError("worker.not_found", 404)
    return row


def _checked_name(
    db: Session, farm_id: uuid.UUID, name: str | None, worker_id: uuid.UUID | None
) -> str:
    cleaned = _clean(name)
    if cleaned is None:
        raise AppError("validation_error", 422, {"name": "labour.worker_name_required"})
    stmt = select(Worker.id).where(Worker.farm_id == farm_id, Worker.name == cleaned)
    if worker_id is not None:
        stmt = stmt.where(Worker.id != worker_id)
    if db.scalar(stmt.limit(1)) is not None:
        raise AppError("validation_error", 422, {"name": "labour.worker_name_taken"})
    return cleaned


def list_workers(db: Session, farm: Farm) -> WorkerListOut:
    rows = db.scalars(
        select(Worker).where(Worker.farm_id == farm.id).order_by(Worker.name, Worker.id)
    ).all()
    return WorkerListOut(workers=[_worker_out(row) for row in rows])


def create_worker(db: Session, farm: Farm, user: AppUser, body: WorkerIn) -> WorkerOut:
    name = _checked_name(db, farm.id, body.name, None)
    row = Worker(
        farm_id=farm.id,
        name=name,
        role=body.role,
        kind=body.kind,
        phone=_clean(body.phone),
        active=body.active,
        version=1,
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    _add_history(db, row=row, user=user, changed=list(_WORKER_FIELDS), reason=None)
    db.commit()
    db.refresh(row)
    return _worker_out(row)


def update_worker(
    db: Session,
    user: AppUser,
    worker_id: uuid.UUID,
    body: WorkerPatch,
    if_match: str | None,
) -> WorkerOut:
    row = _worker_or_404(db, user, worker_id)
    _require_if_match(row.version, if_match)
    before = {field: getattr(row, field) for field in _WORKER_FIELDS}
    if body.name is not None:
        row.name = _checked_name(db, row.farm_id, body.name, row.id)
    if body.role is not None:
        row.role = body.role
    if body.kind is not None:
        row.kind = body.kind
    if "phone" in body.model_fields_set:
        row.phone = _clean(body.phone)
    if body.active is not None:
        row.active = body.active
    changed = [field for field in _WORKER_FIELDS if getattr(row, field) != before[field]]
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(db, row=row, user=user, changed=changed, reason=_clean(body.reason))
    db.commit()
    db.refresh(row)
    return _worker_out(row)


def delete_worker(
    db: Session,
    user: AppUser,
    worker_id: uuid.UUID,
    if_match: str | None,
    reason: str | None = None,
) -> None:
    row = _worker_or_404(db, user, worker_id)
    _require_if_match(row.version, if_match)
    in_use = db.scalar(select(LabourLog.id).where(row.id == any_(LabourLog.worker_ids)).limit(1))
    if in_use is not None:
        raise AppError("labour.worker_in_use", 409)
    row.version += 1
    _add_history(db, row=row, user=user, changed=["deleted"], reason=_clean(reason))
    db.delete(row)
    db.commit()


def _farm_workers(
    db: Session, farm_id: uuid.UUID, worker_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Worker]:
    if not worker_ids:
        return {}
    found = db.scalars(
        select(Worker).where(Worker.id.in_(worker_ids), Worker.farm_id == farm_id)
    ).all()
    return {row.id: row for row in found}


# --- attendance ------------------------------------------------------------


def _attendance_item(row: Attendance, name: str) -> AttendanceItemOut:
    return AttendanceItemOut(
        worker_id=row.worker_id,
        worker_name=name,
        present=row.present,
        hours=row.hours,
        note=row.note,
    )


def get_attendance(db: Session, farm: Farm, on: date) -> AttendanceDayOut:
    rows = db.execute(
        select(Attendance, Worker.name)
        .join(Worker, Worker.id == Attendance.worker_id)
        .where(Attendance.farm_id == farm.id, Attendance.date == on)
        .order_by(Worker.name, Worker.id)
    ).all()
    return AttendanceDayOut(date=on, items=[_attendance_item(row, name) for row, name in rows])


def put_attendance(db: Session, farm: Farm, body: AttendancePut) -> AttendanceDayOut:
    ids = list(dict.fromkeys(item.worker_id for item in body.items))
    workers = _farm_workers(db, farm.id, ids)
    if set(ids) != set(workers):
        raise AppError("validation_error", 422, {"items": "labour.worker_not_in_farm"})
    for item in body.items:
        if item.hours is not None and item.hours < 0:
            raise AppError("validation_error", 422, {"items": "labour.hours_invalid"})
        row = db.get(Attendance, (item.worker_id, body.date))
        if row is None:
            row = Attendance(worker_id=item.worker_id, date=body.date, farm_id=farm.id)
            db.add(row)
        row.present = item.present
        row.hours = item.hours
        row.note = _clean(item.note)
    db.commit()
    return get_attendance(db, farm, body.date)


def attendance_summary(
    db: Session, farm: Farm, date_from: date, date_to: date
) -> AttendanceSummaryOut:
    if date_to < date_from:
        raise AppError("validation_error", 422, {"to": "labour.range_invalid"})
    workers = db.scalars(
        select(Worker).where(Worker.farm_id == farm.id).order_by(Worker.name, Worker.id)
    ).all()
    rows = db.scalars(
        select(Attendance).where(
            Attendance.farm_id == farm.id,
            Attendance.date >= date_from,
            Attendance.date <= date_to,
            Attendance.present.is_(True),
        )
    ).all()
    days: dict[uuid.UUID, int] = {}
    hours: dict[uuid.UUID, Decimal] = {}
    for row in rows:
        days[row.worker_id] = days.get(row.worker_id, 0) + 1
        if row.hours is not None:
            hours[row.worker_id] = hours.get(row.worker_id, Decimal(0)) + row.hours
    return AttendanceSummaryOut(
        date_from=date_from,
        date_to=date_to,
        workers=[
            AttendanceSummaryRowOut(
                worker_id=worker.id,
                worker_name=worker.name,
                days_present=days.get(worker.id, 0),
                hours=hours.get(worker.id, Decimal(0)),
            )
            for worker in workers
        ],
    )


# --- operation labour ------------------------------------------------------


def _headcount(body: OperationLabourIn, worker_ids: list[uuid.UUID]) -> int:
    if body.headcount is not None and worker_ids and body.headcount != len(worker_ids):
        raise AppError("validation_error", 422, {"labour.headcount": "labour.headcount_mismatch"})
    if body.headcount is not None:
        return body.headcount
    if worker_ids:
        return len(worker_ids)
    raise AppError("validation_error", 422, {"labour.headcount": "labour.workers_required"})


def apply_operation_labour(
    db: Session, operation: Operation, body: OperationLabourIn | None
) -> int | None:
    """Replace the operation's labour log; return the head count (None when cleared)."""
    existing = db.scalar(select(LabourLog).where(LabourLog.operation_id == operation.id))
    if body is None:
        if existing is not None:
            db.delete(existing)
            db.flush()
        return None
    worker_ids = list(dict.fromkeys(body.worker_ids or []))
    if set(worker_ids) != set(_farm_workers(db, operation.farm_id, worker_ids)):
        raise AppError("validation_error", 422, {"labour.worker_ids": "labour.worker_not_in_farm"})
    count = _headcount(body, worker_ids)
    try:
        total = calc.labour_hours([(count, body.hours_each)])
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {f"labour.{exc.field}": exc.code}) from None
    row = existing
    if row is None:
        row = LabourLog(farm_id=operation.farm_id, operation_id=operation.id)
        db.add(row)
    row.worker_ids = worker_ids
    row.headcount = body.headcount
    row.hours_each = body.hours_each
    row.total_hours = total
    db.flush()
    return count


def operation_labour_out(db: Session, operation_id: uuid.UUID) -> OperationLabourOut | None:
    row = db.scalar(select(LabourLog).where(LabourLog.operation_id == operation_id))
    if row is None:
        return None
    ids = list(row.worker_ids or [])
    workers = _farm_workers(db, row.farm_id, ids)
    return OperationLabourOut(
        workers=[
            OperationLabourWorkerOut(id=worker_id, name=workers[worker_id].name)
            for worker_id in ids
            if worker_id in workers
        ],
        headcount=row.headcount if row.headcount is not None else len(ids),
        hours_each=row.hours_each,
        total_hours=row.total_hours,
    )


def operation_labour_warnings(db: Session, operation_id: uuid.UUID) -> list[OperationWarningOut]:
    """An inactive worker may be assigned; the operation carries a warning for each."""
    row = db.scalar(select(LabourLog).where(LabourLog.operation_id == operation_id))
    if row is None:
        return []
    ids = list(row.worker_ids or [])
    workers = _farm_workers(db, row.farm_id, ids)
    return [
        OperationWarningOut(code="labour.worker_inactive", worker=workers[worker_id].name)
        for worker_id in ids
        if worker_id in workers and not workers[worker_id].active
    ]


# --- norms -----------------------------------------------------------------


def _season_year(farm: Farm) -> int:
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date().year


def labour_norms(db: Session, farm: Farm, season: int | None) -> LabourNormListOut:
    year = season if season is not None else _season_year(farm)
    rows = db.execute(
        select(LabourLog.total_hours, Operation.type, Operation.area_ha, Block.crop_id)
        .join(Operation, Operation.id == LabourLog.operation_id)
        .join(Block, Block.id == Operation.block_id)
        .where(
            LabourLog.farm_id == farm.id,
            Operation.farm_id == farm.id,
            Operation.date >= date(year, 1, 1),
            Operation.date <= date(year, 12, 31),
        )
    ).all()
    groups: dict[tuple[OperationType, uuid.UUID | None], list[tuple[Decimal, Decimal]]] = {}
    for total_hours, op_type, area_ha, crop_id in rows:
        groups.setdefault((op_type, crop_id), []).append((total_hours, area_ha))
    crop_ids = {crop_id for _type, crop_id in groups if crop_id is not None}
    crops = (
        {row.id: row for row in db.scalars(select(Crop).where(Crop.id.in_(crop_ids))).all()}
        if crop_ids
        else {}
    )
    out: list[LabourNormOut] = []
    for (op_type, crop_id), entries in groups.items():
        hours = sum((entry[0] for entry in entries), Decimal(0))
        area = sum((entry[1] for entry in entries), Decimal(0))
        crop = crops.get(crop_id) if crop_id is not None else None
        out.append(
            LabourNormOut(
                operation_type=op_type,
                crop=None
                if crop is None
                else NormCropOut(
                    id=crop.id,
                    code=crop.code,
                    name={"fr": crop.name_fr, "ar": crop.name_ar, "en": crop.name_en},
                ),
                total_hours=hours,
                total_area_ha=area,
                h_per_ha=calc.labour_norm_h_per_ha(hours, area),
                operations_count=len(entries),
            )
        )
    out.sort(key=lambda row: (row.operation_type.value, row.crop.code if row.crop else ""))
    return LabourNormListOut(season=year, rows=out)
