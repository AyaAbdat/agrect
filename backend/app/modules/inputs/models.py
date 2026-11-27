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
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PriceResource(enum.StrEnum):
    product = "product"
    water_m3 = "water_m3"
    labour_h = "labour_h"
    machine_h = "machine_h"
    energy_kwh = "energy_kwh"
    fuel_l = "fuel_l"


class StockMoveKind(enum.StrEnum):
    purchase = "purchase"
    use = "use"
    adjustment = "adjustment"


class CostSource(enum.StrEnum):
    product = "product"
    labour = "labour"
    machine = "machine"
    water = "water"
    energy = "energy"
    fuel = "fuel"


class CostRefKind(enum.StrEnum):
    operation = "operation"
    irrigation = "irrigation"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Price(Base):
    __tablename__ = "price"
    __table_args__ = (CheckConstraint("dzd_per_unit > 0", name="ck_price_dzd_per_unit_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    resource: Mapped[PriceResource] = mapped_column(
        _pg_enum(PriceResource, "price_resource"),
        nullable=False,
    )
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    dzd_per_unit: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class StockMove(Base):
    __tablename__ = "stock_move"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    kind: Mapped[StockMoveKind] = mapped_column(
        _pg_enum(StockMoveKind, "stock_move_kind"),
        nullable=False,
    )
    operation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operation.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class CostLine(Base):
    __tablename__ = "cost_line"

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
    source: Mapped[CostSource] = mapped_column(
        _pg_enum(CostSource, "cost_source"),
        nullable=False,
    )
    ref_kind: Mapped[CostRefKind] = mapped_column(
        _pg_enum(CostRefKind, "cost_ref_kind"),
        nullable=False,
    )
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    dzd: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    price_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("price.id", ondelete="SET NULL"),
        nullable=True,
    )
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)
