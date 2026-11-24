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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class ProductKind(enum.StrEnum):
    fertiliser = "fertiliser"
    crop_protection = "crop_protection"
    seed = "seed"
    packaging = "packaging"
    other = "other"


class ProductUnit(enum.StrEnum):
    kg = "kg"
    g = "g"
    l = "l"  # noqa: E741
    ml = "ml"
    unit = "unit"


class OperationType(enum.StrEnum):
    fertigation = "fertigation"
    foliar_application = "foliar_application"
    crop_protection_spray = "crop_protection_spray"
    herbicide = "herbicide"
    pruning = "pruning"
    shoot_cluster_thinning = "shoot_cluster_thinning"
    growth_regulator = "growth_regulator"
    girdling = "girdling"
    leaf_removal = "leaf_removal"
    cover_netting = "cover_netting"
    tillage = "tillage"
    sowing = "sowing"
    nitrogen_application = "nitrogen_application"
    other = "other"


class RateBasis(enum.StrEnum):
    per_ha = "per_ha"
    per_100l = "per_100l"
    per_block = "per_block"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (UniqueConstraint("farm_id", "name", name="uq_product_farm_id_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[ProductKind] = mapped_column(_pg_enum(ProductKind, "product_kind"), nullable=False)
    unit: Mapped[ProductUnit] = mapped_column(_pg_enum(ProductUnit, "product_unit"), nullable=False)
    active_ingredient: Mapped[str | None] = mapped_column(Text, nullable=True)
    nutrient_n_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    nutrient_p2o5_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    nutrient_k2o_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    preharvest_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reentry_h: Mapped[int | None] = mapped_column(Integer, nullable=True)
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


class Operation(Base):
    __tablename__ = "operation"

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
    valve_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)),
        nullable=False,
        server_default=text("'{}'"),
    )
    type: Mapped[OperationType] = mapped_column(
        _pg_enum(OperationType, "operation_type"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    area_ha: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    products: Mapped[list["OperationProduct"]] = relationship(
        back_populates="operation",
        cascade="all, delete-orphan",
        order_by="OperationProduct.id",
    )
    safety: Mapped["OperationSafety | None"] = relationship(
        back_populates="operation",
        uselist=False,
        cascade="all, delete-orphan",
    )


class OperationProduct(Base):
    __tablename__ = "operation_product"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("product.id"),
        nullable=False,
        index=True,
    )
    rate: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    rate_unit: Mapped[ProductUnit] = mapped_column(
        _pg_enum(ProductUnit, "product_unit"),
        nullable=False,
    )
    rate_basis: Mapped[RateBasis] = mapped_column(
        _pg_enum(RateBasis, "rate_basis"),
        nullable=False,
    )
    water_l_ha: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    total_qty: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    total_unit: Mapped[ProductUnit] = mapped_column(
        _pg_enum(ProductUnit, "product_unit"),
        nullable=False,
    )

    operation: Mapped[Operation] = relationship(back_populates="products")
    product: Mapped[Product] = relationship()


class OperationSafety(Base):
    __tablename__ = "operation_safety"

    operation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("operation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    preharvest_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reentry_h: Mapped[int | None] = mapped_column(Integer, nullable=True)

    operation: Mapped[Operation] = relationship(back_populates="safety")
