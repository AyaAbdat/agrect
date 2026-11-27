import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WorkerRole(enum.StrEnum):
    """Draft list pending agronomist validation (see DECISIONS)."""

    farm_manager = "farm_manager"
    agronomist = "agronomist"
    irrigation_lead = "irrigation_lead"
    scout = "scout"
    operator = "operator"
    owner = "owner"
    other = "other"


class WorkerKind(enum.StrEnum):
    permanent = "permanent"
    seasonal = "seasonal"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Worker(Base):
    __tablename__ = "worker"
    __table_args__ = (UniqueConstraint("farm_id", "name", name="uq_worker_farm_id_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[WorkerRole] = mapped_column(_pg_enum(WorkerRole, "worker_role"), nullable=False)
    kind: Mapped[WorkerKind] = mapped_column(_pg_enum(WorkerKind, "worker_kind"), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
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


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (CheckConstraint("hours IS NULL OR hours >= 0", name="hours_non_negative"),)

    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("worker.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hours: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class LabourLog(Base):
    __tablename__ = "labour_log"
    __table_args__ = (
        CheckConstraint("hours_each >= 0", name="hours_each_non_negative"),
        CheckConstraint("headcount IS NULL OR headcount >= 0", name="headcount_non_negative"),
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
        unique=True,
    )
    worker_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'"),
    )
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hours_each: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    total_hours: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
