import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class HarvestUnit(enum.StrEnum):
    kg = "kg"
    t = "t"
    crate = "crate"
    bin = "bin"


class HarvestBasis(enum.StrEnum):
    block = "block"
    valve = "valve"
    rows = "rows"
    trees = "trees"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class HarvestEntry(Base):
    __tablename__ = "harvest_entry"

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
    valve_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("valve.id", ondelete="SET NULL"),
        nullable=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    pass_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[HarvestUnit] = mapped_column(_pg_enum(HarvestUnit, "harvest_unit"), nullable=False)
    unit_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    basis: Mapped[HarvestBasis] = mapped_column(
        _pg_enum(HarvestBasis, "harvest_basis"),
        nullable=False,
    )
    basis_count: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    kg: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    kg_ha: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    area_ha: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
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

    quality: Mapped["HarvestQuality | None"] = relationship(
        back_populates="entry",
        uselist=False,
        cascade="all, delete-orphan",
    )


class HarvestQuality(Base):
    __tablename__ = "harvest_quality"

    harvest_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("harvest_entry.id", ondelete="CASCADE"),
        primary_key=True,
    )
    brix: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    size_grade: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    waste_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    moisture_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    protein_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    test_weight_kg_hl: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    entry: Mapped[HarvestEntry] = relationship(back_populates="quality")
