import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MachineType(enum.StrEnum):
    tractor = "tractor"
    sprayer = "sprayer"
    combine = "combine"
    other = "other"


class MachineStatus(enum.StrEnum):
    ok = "ok"
    repair = "repair"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Machine(Base):
    __tablename__ = "machine"
    __table_args__ = (
        UniqueConstraint("farm_id", "name", name="uq_machine_farm_id_name"),
        CheckConstraint(
            "engine_hours_reading IS NULL OR engine_hours_reading >= 0",
            name="engine_hours_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[MachineType] = mapped_column(_pg_enum(MachineType, "machine_type"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[MachineStatus] = mapped_column(
        _pg_enum(MachineStatus, "machine_status"),
        nullable=False,
        default=MachineStatus.ok,
        server_default=text("'ok'"),
    )
    engine_hours_reading: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    reading_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class MachineUse(Base):
    __tablename__ = "machine_use"
    __table_args__ = (
        UniqueConstraint("operation_id", "machine_id", name="uq_machine_use_operation_machine"),
        CheckConstraint("hours > 0", name="hours_positive"),
        CheckConstraint("fuel_l IS NULL OR fuel_l >= 0", name="fuel_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("machine.id"),
        nullable=False,
        index=True,
    )
    hours: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    fuel_l: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)


class Maintenance(Base):
    __tablename__ = "maintenance"
    __table_args__ = (
        CheckConstraint(
            "interval_h IS NOT NULL OR interval_days IS NOT NULL", name="interval_required"
        ),
        CheckConstraint("interval_h IS NULL OR interval_h > 0", name="interval_h_positive"),
        CheckConstraint(
            "interval_days IS NULL OR interval_days > 0", name="interval_days_positive"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("machine.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task: Mapped[str] = mapped_column(Text, nullable=False)
    interval_h: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_done_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_done_h: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
