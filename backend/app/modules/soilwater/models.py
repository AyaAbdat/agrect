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
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TextureMode(enum.StrEnum):
    texture_class = "class"
    percent = "percent"


class Compaction(enum.StrEnum):
    loose = "loose"
    normal = "normal"
    compacted = "compacted"


class InfiltrationSource(enum.StrEnum):
    texture = "texture"
    ring_test = "ring_test"


class KcSource(enum.StrEnum):
    suggested = "suggested"
    entered = "entered"


class IrrigationSource(enum.StrEnum):
    calculated = "calculated"
    measured = "measured"


class DepthBand(enum.StrEnum):
    band_0_30 = "0_30"
    band_30_60 = "30_60"


class SoilFeel(enum.StrEnum):
    dry = "dry"
    slightly_moist = "slightly_moist"
    moist = "moist"
    wet = "wet"


class WbStatus(enum.StrEnum):
    ok = "ok"
    irrigate_soon = "irrigate_soon"
    no_data = "no_data"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class SoilProfile(Base):
    __tablename__ = "soil_profile"
    __table_args__ = (UniqueConstraint("block_id"),)

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
    texture_mode: Mapped[TextureMode] = mapped_column(
        _pg_enum(TextureMode, "texture_mode"),
        nullable=False,
    )
    texture_class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("soil_texture_class.id"),
        nullable=True,
    )
    sand_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    silt_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    clay_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    theta_fc: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    theta_wp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    root_depth_m: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    dry_down_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    full_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    organic_matter_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    compaction: Mapped[Compaction | None] = mapped_column(
        _pg_enum(Compaction, "compaction"),
        nullable=True,
    )
    infiltration_mm_h: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    infiltration_source: Mapped[InfiltrationSource | None] = mapped_column(
        _pg_enum(InfiltrationSource, "infiltration_source"),
        nullable=True,
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


class IrrigationSettings(Base):
    __tablename__ = "irrigation_settings"
    __table_args__ = (UniqueConstraint("block_id"),)

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
    efficiency: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    kc: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    kc_source: Mapped[KcSource | None] = mapped_column(
        _pg_enum(KcSource, "kc_source"),
        nullable=True,
    )
    stage_override_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
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


class IrrigationEvent(Base):
    __tablename__ = "irrigation_event"
    __table_args__ = (CheckConstraint("cardinality(valve_ids) > 0", name="valve_ids_not_empty"),)

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
        index=True,
    )
    valve_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    depth_mm: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    volume_m3: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    soil_mm: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    runoff_mm: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    source: Mapped[IrrigationSource] = mapped_column(
        _pg_enum(IrrigationSource, "irrigation_source"),
        nullable=False,
    )
    entered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id"),
        nullable=False,
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


class SoilCheck(Base):
    __tablename__ = "soil_check"

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
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    depth_band: Mapped[DepthBand] = mapped_column(_pg_enum(DepthBand, "depth_band"), nullable=False)
    feel: Mapped[SoilFeel] = mapped_column(_pg_enum(SoilFeel, "soil_feel"), nullable=False)
    reset_depletion_mm: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class WaterBalanceDaily(Base):
    __tablename__ = "water_balance_daily"

    block_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("block.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    et0_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    kc: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    etc_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rain_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    irrigation_soil_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    runoff_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    drainage_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    depletion_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    taw_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    raw_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[WbStatus] = mapped_column(_pg_enum(WbStatus, "wb_status"), nullable=False)
    is_forecast: Mapped[bool] = mapped_column(Boolean, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
