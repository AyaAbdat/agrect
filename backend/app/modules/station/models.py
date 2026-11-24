import enum
import uuid
from datetime import datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WaterSourceKind(enum.StrEnum):
    borehole = "borehole"
    basin = "basin"
    network = "network"


class CapacityChoice(enum.StrEnum):
    priority = "priority"
    share = "share"
    more_shifts = "more_shifts"


class CapacityMode(enum.StrEnum):
    today = "today"
    peak_week = "peak_week"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Station(Base):
    __tablename__ = "station"
    __table_args__ = (UniqueConstraint("farm_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Station",
        server_default=text("'Station'"),
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


class WaterSource(Base):
    __tablename__ = "water_source"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[WaterSourceKind] = mapped_column(
        _pg_enum(WaterSourceKind, "water_source_kind"),
        nullable=False,
    )
    ec_ds_m: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    basin_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)


class Pump(Base):
    __tablename__ = "pump"
    __table_args__ = (
        UniqueConstraint("station_id", "name"),
        CheckConstraint("flow_m3h > 0", name="flow_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("station.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    flow_m3h: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    serves_all_blocks: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    pressure_bar: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    water_source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("water_source.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))


class PumpBlock(Base):
    __tablename__ = "pump_block"

    pump_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pump.id", ondelete="CASCADE"),
        primary_key=True,
    )
    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("block.id", ondelete="CASCADE"),
        primary_key=True,
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class PumpWindow(Base):
    __tablename__ = "pump_window"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pump_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pump.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)


class CapacityDecision(Base):
    __tablename__ = "capacity_decision"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    choice: Mapped[CapacityChoice] = mapped_column(
        _pg_enum(CapacityChoice, "capacity_choice"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    block_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=True,
    )
    mode: Mapped[CapacityMode] = mapped_column(
        _pg_enum(CapacityMode, "capacity_mode"),
        nullable=False,
    )
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
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
