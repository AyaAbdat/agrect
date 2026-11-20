import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SeasonStatus(enum.StrEnum):
    open = "open"
    closed = "closed"


class PredictionLabel(enum.StrEnum):
    observed = "observed"
    predicted = "predicted"
    not_enough_data = "not_enough_data"
    beyond_data = "beyond_data"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class BlockSeason(Base):
    __tablename__ = "block_season"
    __table_args__ = (UniqueConstraint("block_id", "year"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("block.id", ondelete="CASCADE"),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_stage_def_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stage_def.id", ondelete="SET NULL"),
        nullable=True,
    )
    start_observed: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[SeasonStatus] = mapped_column(
        _pg_enum(SeasonStatus, "season_status"),
        nullable=False,
        default=SeasonStatus.open,
    )


class StageObservation(Base):
    __tablename__ = "stage_observation"
    __table_args__ = (UniqueConstraint("block_season_id", "stage_def_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    block_season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("block_season.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stage_def.id", ondelete="CASCADE"),
        nullable=False,
    )
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    share_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class StagePrediction(Base):
    __tablename__ = "stage_prediction"

    block_season_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("block_season.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stage_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stage_def.id", ondelete="CASCADE"),
        primary_key=True,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[PredictionLabel] = mapped_column(
        _pg_enum(PredictionLabel, "prediction_label"),
        nullable=False,
    )
    predicted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    earliest: Mapped[date | None] = mapped_column(Date, nullable=True)
    latest: Mapped[date | None] = mapped_column(Date, nullable=True)
    dd_needed: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    dd_counted: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
