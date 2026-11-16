import enum
import uuid
from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.modules.farms.models import Farm


class BlockStatus(enum.StrEnum):
    draft = "draft"
    complete = "complete"
    archived = "archived"


class DensityInput(enum.StrEnum):
    spacing = "spacing"
    density = "density"
    count = "count"


class IrrigationSystem(enum.StrEnum):
    drip = "drip"
    subsurface_drip = "subsurface_drip"
    micro_sprinkler = "micro_sprinkler"
    bubbler = "bubbler"
    sprinkler = "sprinkler"


class FlowEntryMode(enum.StrEnum):
    layout = "layout"
    per_tree = "per_tree"
    typed_flow = "typed_flow"


class TypedFlowBasis(enum.StrEnum):
    block = "block"
    ha = "ha"
    valve = "valve"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Block(Base):
    __tablename__ = "block"
    __table_args__ = (UniqueConstraint("farm_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[BlockStatus] = mapped_column(
        Enum(
            BlockStatus,
            name="block_status",
            native_enum=True,
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        nullable=False,
        default=BlockStatus.draft,
        server_default=text("'draft'"),
    )
    outline: Mapped[WKBElement | None] = mapped_column(
        Geometry("POLYGON", srid=4326),
        nullable=True,
    )
    row_line: Mapped[WKBElement | None] = mapped_column(
        Geometry("LINESTRING", srid=4326),
        nullable=True,
    )
    gross_area_ha: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    row_bearing_deg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    net_area_ha: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    rows_total: Mapped[int | None] = mapped_column(nullable=True)
    crop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id"),
        nullable=True,
    )
    training_system_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_system.id"),
        nullable=True,
    )
    training_other: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    farm: Mapped[Farm] = relationship()


class Planting(Base):
    __tablename__ = "planting"

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
    variety_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variety.id"),
        nullable=True,
    )
    variety_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    rootstock: Mapped[str | None] = mapped_column(Text, nullable=True)
    planting_year: Mapped[int | None] = mapped_column(nullable=True)
    density_input: Mapped[DensityInput | None] = mapped_column(
        _pg_enum(DensityInput, "density_input"),
        nullable=True,
    )
    row_spacing_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    tree_spacing_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    trees_per_ha: Mapped[int | None] = mapped_column(nullable=True)
    trees_count: Mapped[int | None] = mapped_column(nullable=True)
    area_ha: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    sort: Mapped[int] = mapped_column(nullable=False)
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class IrrigationLayout(Base):
    __tablename__ = "irrigation_layout"
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
    system: Mapped[IrrigationSystem] = mapped_column(
        _pg_enum(IrrigationSystem, "irrigation_system"),
        nullable=False,
    )
    entry_mode: Mapped[FlowEntryMode] = mapped_column(
        _pg_enum(FlowEntryMode, "flow_entry_mode"),
        nullable=False,
    )
    laterals_per_row: Mapped[int | None] = mapped_column(nullable=True)
    emitter_spacing_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    emitter_flow_lph: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    emitters_per_tree: Mapped[int | None] = mapped_column(nullable=True)
    flow_per_emitter_lph: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    typed_flow_m3h: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    typed_flow_basis: Mapped[TypedFlowBasis | None] = mapped_column(
        _pg_enum(TypedFlowBasis, "typed_flow_basis"),
        nullable=True,
    )
    flow_meter: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    q_ha_m3h: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    q_block_m3h: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    rate_mm_h: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class Valve(Base):
    __tablename__ = "valve"

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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort: Mapped[int] = mapped_column(nullable=False)
    row_from: Mapped[int] = mapped_column(nullable=False)
    row_to: Mapped[int] = mapped_column(nullable=False)
    typed_q_m3h: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    area_ha: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    q_m3h: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    inputs_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
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


class RecordVersion(Base):
    __tablename__ = "record_version"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id"),
        nullable=False,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
