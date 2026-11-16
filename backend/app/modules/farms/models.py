import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from geoalchemy2.elements import WKBElement
from sqlalchemy import DateTime, Enum, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WeatherSource(enum.StrEnum):
    station = "station"
    service = "service"


class Farm(Base):
    __tablename__ = "farm"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("app_user.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[WKBElement | None] = mapped_column(
        Geometry("POINT", srid=4326),
        nullable=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="Africa/Algiers",
        server_default=text("'Africa/Algiers'"),
    )
    weather_source: Mapped[WeatherSource] = mapped_column(
        Enum(
            WeatherSource,
            name="weather_source",
            native_enum=True,
            values_callable=lambda choices: [choice.value for choice in choices],
        ),
        nullable=False,
        default=WeatherSource.service,
        server_default=text("'service'"),
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
