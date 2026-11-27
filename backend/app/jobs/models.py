import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class JobStatus(enum.StrEnum):
    ok = "ok"
    error = "error"


class JobRun(Base):
    """One run of a background job, for one farm (farm_id) or for the server (null)."""

    __tablename__ = "job_run"
    __table_args__ = (Index("ix_job_run_job_farm_started", "job", "farm_id", "started_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job: Mapped[str] = mapped_column(String(64), nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            native_enum=True,
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
