import enum
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class GddMethod(enum.StrEnum):
    average = "average"
    single_sine = "single_sine"


def _pg_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda choices: [choice.value for choice in choices],
    )


_GDD_METHOD = _pg_enum(GddMethod, "gdd_method")


class WeatherHourly(Base):
    __tablename__ = "weather_hourly"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    temp_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rh_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rain_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rain_prob_pct: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    wind_ms: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    gust_ms: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    wind_dir_deg: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rad_wm2: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    et0_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    dewpoint_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    vpd_kpa: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    is_forecast: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="estimated",
        server_default=text("'estimated'"),
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WeatherDaily(Base):
    __tablename__ = "weather_daily"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    tmin_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tmax_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tmean_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rh_min: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rh_max: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rain_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    et0_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    vpd_max_kpa: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    frost_h: Mapped[int | None] = mapped_column(nullable=True)
    heat_h: Mapped[int | None] = mapped_column(nullable=True)
    chill_h: Mapped[int | None] = mapped_column(nullable=True)
    chill_portions: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    hours_count: Mapped[int] = mapped_column(nullable=False)
    is_forecast: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="estimated",
        server_default=text("'estimated'"),
    )
    inputs_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class HistoryDaily(Base):
    __tablename__ = "history_daily"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        primary_key=True,
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    tmin_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    tmax_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    rain_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    et0_mm: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    source: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="estimated",
        server_default=text("'estimated'"),
    )
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FarmThresholds(Base):
    __tablename__ = "farm_thresholds"

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        primary_key=True,
    )
    frost_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    heat_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    vpd_limit_kpa: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    chill_season_start: Mapped[date | None] = mapped_column(Date, nullable=True)


class GddSetting(Base):
    __tablename__ = "gdd_setting"
    __table_args__ = (UniqueConstraint("farm_id", "crop_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm.id", ondelete="CASCADE"),
        nullable=False,
    )
    crop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("crop.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_c: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    upper_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    method: Mapped[GddMethod] = mapped_column(_GDD_METHOD, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class GddSettingBlock(Base):
    __tablename__ = "gdd_setting_block"
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
    base_c: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    upper_c: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    method: Mapped[GddMethod] = mapped_column(_GDD_METHOD, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1, server_default=text("1"))


@dataclass(frozen=True, slots=True)
class EffectiveGddSetting:
    """Degree-day setting that applies to one block.

    A block override wins over the crop setting. ``override`` is true only
    when the values come from ``gdd_setting_block``.
    """

    base_c: Decimal
    upper_c: Decimal | None
    method: GddMethod
    start_date: date | None
    override: bool
