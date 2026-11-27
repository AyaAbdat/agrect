"""Equipment: machines, machine use per operation, fuel, work rate, maintenance due.

Source: AGRECT system design — Equipment.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import AppUser
from app.modules.equipment import calc
from app.modules.equipment.models import Machine, MachineStatus, MachineUse, Maintenance
from app.modules.equipment.schemas import (
    MachineBriefOut,
    MachineDetailOut,
    MachineIn,
    MachineListItemOut,
    MachineListOut,
    MachineOut,
    MachinePatch,
    MachineSeasonUseOut,
    MaintenanceDoneIn,
    MaintenanceDueOut,
    MaintenanceIn,
    MaintenanceListOut,
    MaintenanceOut,
    MaintenancePatch,
)
from app.modules.farms.models import Farm
from app.modules.operations.models import Operation
from app.modules.operations.schemas import (
    OperationMachineIn,
    OperationMachineOut,
    OperationWarningOut,
)
from app.modules.registry.models import RecordVersion

_ENTITY_MACHINE = "machine"
_ENTITY_MAINTENANCE = "maintenance"
_MACHINE_FIELDS = ("type", "name", "status", "engine_hours_reading", "reading_date")
_MAINTENANCE_FIELDS = ("task", "interval_h", "interval_days", "last_done_date", "last_done_h")


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
    farm_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    version: int,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=farm_id,
            entity_type=entity_type,
            entity_id=entity_id,
            version=version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


def _farm_today(farm: Farm) -> date:
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date()


def _non_negative(value: Decimal | None, field: str) -> None:
    if value is not None and value < 0:
        raise AppError("validation_error", 422, {field: "equipment.hours_invalid"})


# --- machines --------------------------------------------------------------


def _machine_out(row: Machine) -> MachineOut:
    return MachineOut(
        id=row.id,
        farm_id=row.farm_id,
        type=row.type,
        name=row.name,
        status=row.status,
        engine_hours_reading=row.engine_hours_reading,
        reading_date=row.reading_date,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _owned_farm(db: Session, user: AppUser, farm_id: uuid.UUID, code: str) -> Farm:
    farm = db.get(Farm, farm_id)
    if farm is None or farm.owner_user_id != user.id:
        raise AppError(code, 404)
    return farm


def _machine_or_404(db: Session, user: AppUser, machine_id: uuid.UUID) -> tuple[Machine, Farm]:
    row = db.get(Machine, machine_id)
    if row is None:
        raise AppError("machine.not_found", 404)
    return row, _owned_farm(db, user, row.farm_id, "machine.not_found")


def _checked_name(
    db: Session, farm_id: uuid.UUID, name: str | None, machine_id: uuid.UUID | None
) -> str:
    cleaned = _clean(name)
    if cleaned is None:
        raise AppError("validation_error", 422, {"name": "equipment.machine_name_required"})
    stmt = select(Machine.id).where(Machine.farm_id == farm_id, Machine.name == cleaned)
    if machine_id is not None:
        stmt = stmt.where(Machine.id != machine_id)
    if db.scalar(stmt.limit(1)) is not None:
        raise AppError("validation_error", 422, {"name": "equipment.machine_name_taken"})
    return cleaned


def list_machines(db: Session, farm: Farm) -> MachineListOut:
    """Machines with current engine hours and maintenance due, in three queries in total."""
    rows = db.scalars(
        select(Machine).where(Machine.farm_id == farm.id).order_by(Machine.name, Machine.id)
    ).all()
    uses = db.execute(
        select(MachineUse.machine_id, MachineUse.hours, Operation.date)
        .join(Operation, Operation.id == MachineUse.operation_id)
        .where(MachineUse.farm_id == farm.id)
    ).all()
    tasks = db.scalars(
        select(Maintenance)
        .where(Maintenance.farm_id == farm.id)
        .order_by(Maintenance.task, Maintenance.id)
    ).all()
    hours_by_machine: dict[uuid.UUID, list[tuple[Decimal, date]]] = {}
    for machine_id, hours, on in uses:
        hours_by_machine.setdefault(machine_id, []).append((hours, on))
    tasks_by_machine: dict[uuid.UUID, list[Maintenance]] = {}
    for task in tasks:
        tasks_by_machine.setdefault(task.machine_id, []).append(task)
    today = _farm_today(farm)
    items: list[MachineListItemOut] = []
    for row in rows:
        current = _engine_hours_from(row, hours_by_machine.get(row.id, []))
        items.append(
            MachineListItemOut(
                **_machine_out(row).__dict__,
                current_engine_hours=current,
                current_engine_hours_source=None if current is None else "calculated",
                maintenance=[
                    _maintenance_out(task, row, current, today)
                    for task in tasks_by_machine.get(row.id, [])
                ],
            )
        )
    return MachineListOut(machines=items)


def _engine_hours_from(machine: Machine, uses: list[tuple[Decimal, date]]) -> Decimal | None:
    """Same rule as ``_engine_hours`` on preloaded (hours, operation date) pairs."""
    if machine.engine_hours_reading is None:
        return None
    after = [
        hours for hours, on in uses if machine.reading_date is None or on > machine.reading_date
    ]
    return calc.current_engine_hours(machine.engine_hours_reading, after)


def create_machine(db: Session, farm: Farm, user: AppUser, body: MachineIn) -> MachineOut:
    name = _checked_name(db, farm.id, body.name, None)
    _non_negative(body.engine_hours_reading, "engine_hours_reading")
    row = Machine(
        farm_id=farm.id,
        type=body.type,
        name=name,
        status=body.status,
        engine_hours_reading=body.engine_hours_reading,
        reading_date=body.reading_date,
        version=1,
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    _add_history(
        db,
        farm_id=farm.id,
        entity_type=_ENTITY_MACHINE,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=list(_MACHINE_FIELDS),
        reason=None,
    )
    db.commit()
    db.refresh(row)
    return _machine_out(row)


def update_machine(
    db: Session,
    user: AppUser,
    machine_id: uuid.UUID,
    body: MachinePatch,
    if_match: str | None,
) -> MachineOut:
    row, _farm = _machine_or_404(db, user, machine_id)
    _require_if_match(row.version, if_match)
    before = {field: getattr(row, field) for field in _MACHINE_FIELDS}
    if body.name is not None:
        row.name = _checked_name(db, row.farm_id, body.name, row.id)
    if body.type is not None:
        row.type = body.type
    if body.status is not None:
        row.status = body.status
    if "engine_hours_reading" in body.model_fields_set:
        _non_negative(body.engine_hours_reading, "engine_hours_reading")
        row.engine_hours_reading = body.engine_hours_reading
    if "reading_date" in body.model_fields_set:
        row.reading_date = body.reading_date
    changed = [field for field in _MACHINE_FIELDS if getattr(row, field) != before[field]]
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_MACHINE,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=changed,
        reason=_clean(body.reason),
    )
    db.commit()
    db.refresh(row)
    return _machine_out(row)


def delete_machine(
    db: Session,
    user: AppUser,
    machine_id: uuid.UUID,
    if_match: str | None,
    reason: str | None = None,
) -> None:
    row, _farm = _machine_or_404(db, user, machine_id)
    _require_if_match(row.version, if_match)
    in_use = db.scalar(select(MachineUse.id).where(MachineUse.machine_id == row.id).limit(1))
    if in_use is not None:
        raise AppError("equipment.machine_in_use", 409)
    row.version += 1
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_MACHINE,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=["deleted"],
        reason=_clean(reason),
    )
    db.delete(row)
    db.commit()


def _engine_hours(db: Session, machine: Machine) -> Decimal | None:
    """Last reading + machine hours logged on operations dated after the reading."""
    if machine.engine_hours_reading is None:
        return None
    stmt = (
        select(MachineUse.hours)
        .join(Operation, Operation.id == MachineUse.operation_id)
        .where(MachineUse.machine_id == machine.id)
    )
    if machine.reading_date is not None:
        stmt = stmt.where(Operation.date > machine.reading_date)
    return calc.current_engine_hours(machine.engine_hours_reading, db.scalars(stmt).all())


def _season_use(db: Session, machine: Machine, season: int) -> MachineSeasonUseOut:
    rows = db.execute(
        select(MachineUse.hours, MachineUse.fuel_l, Operation.area_ha)
        .join(Operation, Operation.id == MachineUse.operation_id)
        .where(
            MachineUse.machine_id == machine.id,
            Operation.date >= date(season, 1, 1),
            Operation.date <= date(season, 12, 31),
        )
    ).all()
    hours = sum((row[0] for row in rows), Decimal(0))
    fuel = sum((row[1] for row in rows if row[1] is not None), Decimal(0))
    area = sum((row[2] for row in rows), Decimal(0))
    return MachineSeasonUseOut(
        season=season,
        uses_count=len(rows),
        hours=hours,
        fuel_l=fuel,
        area_ha=area,
        avg_work_rate_ha_h=calc.work_rate_ha_h(area, hours),
    )


def get_machine(
    db: Session, user: AppUser, machine_id: uuid.UUID, season: int | None
) -> MachineDetailOut:
    row, farm = _machine_or_404(db, user, machine_id)
    today = _farm_today(farm)
    current = _engine_hours(db, row)
    tasks = db.scalars(
        select(Maintenance)
        .where(Maintenance.machine_id == row.id)
        .order_by(Maintenance.task, Maintenance.id)
    ).all()
    base = _machine_out(row)
    return MachineDetailOut(
        **base.__dict__,
        current_engine_hours=current,
        current_engine_hours_source=None if current is None else "calculated",
        uses_this_season=_season_use(db, row, season if season is not None else today.year),
        maintenance=[_maintenance_out(task, row, current, today) for task in tasks],
    )


# --- maintenance -----------------------------------------------------------


def _maintenance_out(
    row: Maintenance, machine: Machine, current_h: Decimal | None, today: date
) -> MaintenanceOut:
    due = calc.maintenance_due(
        row.last_done_h,
        row.interval_h,
        current_h,
        row.last_done_date,
        row.interval_days,
        today,
    )
    return MaintenanceOut(
        id=row.id,
        farm_id=row.farm_id,
        machine=MachineBriefOut(id=machine.id, name=machine.name),
        task=row.task,
        interval_h=row.interval_h,
        interval_days=row.interval_days,
        last_done_date=row.last_done_date,
        last_done_h=row.last_done_h,
        due=MaintenanceDueOut(
            due_by_hours=due.due_by_hours,
            due_by_date=due.due_by_date,
            next_due_h=due.next_due_h,
            next_due_date=due.next_due_date,
            overdue=due.overdue,
        ),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _maintenance_or_404(
    db: Session, user: AppUser, maintenance_id: uuid.UUID
) -> tuple[Maintenance, Machine, Farm]:
    row = db.get(Maintenance, maintenance_id)
    if row is None:
        raise AppError("maintenance.not_found", 404)
    farm = _owned_farm(db, user, row.farm_id, "maintenance.not_found")
    machine = db.get(Machine, row.machine_id)
    if machine is None:
        raise AppError("maintenance.not_found", 404)
    return row, machine, farm


def _check_maintenance(row: Maintenance) -> None:
    if _clean(row.task) is None:
        raise AppError("validation_error", 422, {"task": "equipment.task_required"})
    if row.interval_h is None and row.interval_days is None:
        raise AppError("validation_error", 422, {"interval_h": "equipment.interval_required"})
    if row.interval_h is not None and row.interval_h <= 0:
        raise AppError("validation_error", 422, {"interval_h": "equipment.interval_invalid"})
    _non_negative(row.last_done_h, "last_done_h")


def _maintenance_result(db: Session, row: Maintenance, machine: Machine, farm: Farm):
    return _maintenance_out(row, machine, _engine_hours(db, machine), _farm_today(farm))


def list_maintenance(db: Session, user: AppUser, machine_id: uuid.UUID) -> MaintenanceListOut:
    machine, farm = _machine_or_404(db, user, machine_id)
    current = _engine_hours(db, machine)
    today = _farm_today(farm)
    rows = db.scalars(
        select(Maintenance)
        .where(Maintenance.machine_id == machine.id)
        .order_by(Maintenance.task, Maintenance.id)
    ).all()
    return MaintenanceListOut(
        items=[_maintenance_out(row, machine, current, today) for row in rows]
    )


def create_maintenance(
    db: Session, user: AppUser, machine_id: uuid.UUID, body: MaintenanceIn
) -> MaintenanceOut:
    machine, farm = _machine_or_404(db, user, machine_id)
    row = Maintenance(
        farm_id=farm.id,
        machine_id=machine.id,
        task=_clean(body.task) or "",
        interval_h=body.interval_h,
        interval_days=body.interval_days,
        last_done_date=body.last_done_date,
        last_done_h=body.last_done_h,
        version=1,
        updated_at=datetime.now(UTC),
    )
    _check_maintenance(row)
    db.add(row)
    db.flush()
    _add_history(
        db,
        farm_id=farm.id,
        entity_type=_ENTITY_MAINTENANCE,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=list(_MAINTENANCE_FIELDS),
        reason=None,
    )
    db.commit()
    db.refresh(row)
    return _maintenance_result(db, row, machine, farm)


def _save_maintenance(
    db: Session,
    user: AppUser,
    row: Maintenance,
    before: dict[str, object],
    reason: str | None,
) -> None:
    _check_maintenance(row)
    changed = [field for field in _MAINTENANCE_FIELDS if getattr(row, field) != before[field]]
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_MAINTENANCE,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=changed,
        reason=reason,
    )
    db.commit()
    db.refresh(row)


def update_maintenance(
    db: Session,
    user: AppUser,
    maintenance_id: uuid.UUID,
    body: MaintenancePatch,
    if_match: str | None,
) -> MaintenanceOut:
    row, machine, farm = _maintenance_or_404(db, user, maintenance_id)
    _require_if_match(row.version, if_match)
    before: dict[str, object] = {field: getattr(row, field) for field in _MAINTENANCE_FIELDS}
    if body.task is not None:
        row.task = _clean(body.task) or ""
    for field in ("interval_h", "interval_days", "last_done_date", "last_done_h"):
        if field in body.model_fields_set:
            setattr(row, field, getattr(body, field))
    _save_maintenance(db, user, row, before, _clean(body.reason))
    return _maintenance_result(db, row, machine, farm)


def mark_maintenance_done(
    db: Session,
    user: AppUser,
    maintenance_id: uuid.UUID,
    body: MaintenanceDoneIn,
    if_match: str | None,
) -> MaintenanceOut:
    row, machine, farm = _maintenance_or_404(db, user, maintenance_id)
    _require_if_match(row.version, if_match)
    before: dict[str, object] = {field: getattr(row, field) for field in _MAINTENANCE_FIELDS}
    row.last_done_date = body.date
    row.last_done_h = (
        body.engine_hours if body.engine_hours is not None else _engine_hours(db, machine)
    )
    _save_maintenance(db, user, row, before, None)
    return _maintenance_result(db, row, machine, farm)


def delete_maintenance(
    db: Session,
    user: AppUser,
    maintenance_id: uuid.UUID,
    if_match: str | None,
    reason: str | None = None,
) -> None:
    row, _machine, _farm = _maintenance_or_404(db, user, maintenance_id)
    _require_if_match(row.version, if_match)
    row.version += 1
    _add_history(
        db,
        farm_id=row.farm_id,
        entity_type=_ENTITY_MAINTENANCE,
        entity_id=row.id,
        version=row.version,
        user=user,
        changed=["deleted"],
        reason=_clean(reason),
    )
    db.delete(row)
    db.commit()


def farm_maintenance_due(db: Session, farm: Farm) -> MaintenanceListOut:
    today = _farm_today(farm)
    machines = db.scalars(
        select(Machine).where(Machine.farm_id == farm.id).order_by(Machine.name, Machine.id)
    ).all()
    items: list[MaintenanceOut] = []
    for machine in machines:
        current = _engine_hours(db, machine)
        tasks = db.scalars(
            select(Maintenance)
            .where(Maintenance.machine_id == machine.id)
            .order_by(Maintenance.task, Maintenance.id)
        ).all()
        for task in tasks:
            out = _maintenance_out(task, machine, current, today)
            if out.due.due_by_hours or out.due.due_by_date:
                items.append(out)
    return MaintenanceListOut(items=items)


# --- operation machines ----------------------------------------------------


def apply_operation_machines(
    db: Session, operation: Operation, lines: list[OperationMachineIn]
) -> None:
    """Replace the operation's machine uses with ``lines`` (an empty list clears them)."""
    ids = [line.machine_id for line in lines]
    if len(set(ids)) != len(ids):
        raise AppError("validation_error", 422, {"machines": "equipment.machine_duplicate"})
    found = (
        db.scalars(
            select(Machine.id).where(Machine.id.in_(ids), Machine.farm_id == operation.farm_id)
        ).all()
        if ids
        else []
    )
    if set(found) != set(ids):
        raise AppError("validation_error", 422, {"machines": "equipment.machine_not_in_farm"})
    for line in lines:
        if line.hours <= 0:
            raise AppError("validation_error", 422, {"machines.hours": "equipment.hours_invalid"})
        if line.fuel_l is not None and line.fuel_l < 0:
            raise AppError("validation_error", 422, {"machines.fuel_l": "equipment.fuel_invalid"})
    for old in db.scalars(select(MachineUse).where(MachineUse.operation_id == operation.id)):
        db.delete(old)
    db.flush()
    for line in lines:
        db.add(
            MachineUse(
                farm_id=operation.farm_id,
                operation_id=operation.id,
                machine_id=line.machine_id,
                hours=line.hours,
                fuel_l=line.fuel_l,
            )
        )
    db.flush()


def _operation_uses(db: Session, operation_id: uuid.UUID) -> list[tuple[MachineUse, Machine]]:
    rows = db.execute(
        select(MachineUse, Machine)
        .join(Machine, Machine.id == MachineUse.machine_id)
        .where(MachineUse.operation_id == operation_id)
        .order_by(Machine.name, Machine.id)
    ).all()
    return [(use, machine) for use, machine in rows]


def operation_machines_out(db: Session, operation: Operation) -> list[OperationMachineOut]:
    return [
        OperationMachineOut(
            id=machine.id,
            name=machine.name,
            hours=use.hours,
            fuel_l=use.fuel_l,
            work_rate_ha_h=calc.work_rate_ha_h(operation.area_ha, use.hours),
        )
        for use, machine in _operation_uses(db, operation.id)
    ]


def operation_machine_warnings(db: Session, operation_id: uuid.UUID) -> list[OperationWarningOut]:
    return [
        OperationWarningOut(code="equipment.machine_in_repair", machine=machine.name)
        for _use, machine in _operation_uses(db, operation_id)
        if machine.status == MachineStatus.repair
    ]
