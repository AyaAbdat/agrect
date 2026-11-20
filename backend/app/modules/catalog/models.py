import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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
from app.modules.weather.models import GddMethod


class CropKind(enum.StrEnum):
    perennial = "perennial"
    annual = "annual"


class CropScaleCode(enum.StrEnum):
    el = "el"
    bbch = "bbch"
    bbch_olive = "bbch_olive"
    zadoks = "zadoks"


class StageDdSource(enum.StrEnum):
    literature = "literature"
    farm_seasons = "farm_seasons"
    entered = "entered"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str, *, create_type: bool = True) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        create_type=create_type,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


class Crop(Base):
    __tablename__ = "crop"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[CropKind] = mapped_column(
        Enum(
            CropKind,
            name="crop_kind",
            native_enum=True,
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        nullable=False,
    )
    sort: Mapped[int] = mapped_column(nullable=False)
    name_fr: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
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


class Variety(Base):
    __tablename__ = "variety"
    __table_args__ = (UniqueConstraint("crop_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sort: Mapped[int] = mapped_column(nullable=False)
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


class TrainingSystem(Base):
    __tablename__ = "training_system"
    __table_args__ = (UniqueConstraint("crop_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    sort: Mapped[int] = mapped_column(nullable=False)
    name_fr: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    description_fr: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str] = mapped_column(Text, nullable=False)
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


class SoilTextureClass(Base):
    __tablename__ = "soil_texture_class"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    sort: Mapped[int] = mapped_column(nullable=False)
    name_fr: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    theta_fc_min: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    theta_fc_max: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    theta_wp_min: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    theta_wp_max: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    theta_fc: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    theta_wp: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class CropScale(Base):
    """One phenology scale per crop. The PostgreSQL enum is crop_scale_code.

    The table name crop_scale already creates a composite type of that name,
    so the scale enum cannot reuse it.
    """

    __tablename__ = "crop_scale"

    crop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id", ondelete="CASCADE"),
        primary_key=True,
    )
    scale: Mapped[CropScaleCode] = mapped_column(
        _pg_enum(CropScaleCode, "crop_scale_code"),
        nullable=False,
    )
    citation: Mapped[str] = mapped_column(Text, nullable=False)


class StageDef(Base):
    __tablename__ = "stage_def"
    __table_args__ = (UniqueConstraint("crop_id", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    sort: Mapped[int] = mapped_column(nullable=False)
    name_fr: Mapped[str] = mapped_column(String(255), nullable=False)
    name_ar: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False)
    description_fr: Mapped[str] = mapped_column(Text, nullable=False)
    description_ar: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str] = mapped_column(Text, nullable=False)


class StageDd(Base):
    __tablename__ = "stage_dd"
    __table_args__ = (
        CheckConstraint("dd_value > 0", name="dd_must_be_positive"),
        CheckConstraint(
            "(farm_id IS NULL AND citation IS NOT NULL AND btrim(citation) <> '' "
            "AND source_kind <> 'entered') "
            "OR (farm_id IS NOT NULL AND source_kind = 'entered')",
            name="global_cited_or_farm_entered",
        ),
        Index(
            "uq_stage_dd_global_stage",
            "stage_def_id",
            unique=True,
            postgresql_where=text("farm_id IS NULL AND variety_id IS NULL"),
        ),
        Index(
            "uq_stage_dd_farm_stage",
            "farm_id",
            "stage_def_id",
            unique=True,
            postgresql_where=text("farm_id IS NOT NULL"),
        ),
        Index(
            "uq_stage_dd_variety_stage",
            "variety_id",
            "stage_def_id",
            unique=True,
            postgresql_where=text("variety_id IS NOT NULL AND farm_id IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    crop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variety_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variety.id", ondelete="CASCADE"),
        nullable=True,
    )
    stage_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stage_def.id", ondelete="CASCADE"),
        nullable=False,
    )
    dd_value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    base_c: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    upper_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    method: Mapped[GddMethod] = mapped_column(
        _pg_enum(GddMethod, "gdd_method", create_type=False),
        nullable=False,
    )
    source_kind: Mapped[StageDdSource] = mapped_column(
        _pg_enum(StageDdSource, "stage_dd_source"),
        nullable=False,
    )
    citation: Mapped[str | None] = mapped_column(Text, nullable=True)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )


class VarietyChill(Base):
    __tablename__ = "variety_chill"

    variety_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("variety.id", ondelete="CASCADE"),
        primary_key=True,
    )
    chill_h: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    chill_portions: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    citation: Mapped[str] = mapped_column(Text, nullable=False)


class FarmStagePref(Base):
    __tablename__ = "farm_stage_pref"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        primary_key=True,
    )
    stage_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stage_def.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False)
    local_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
