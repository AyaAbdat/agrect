"""Import every module's models here so Alembic autogenerate sees them."""

from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop, SoilTextureClass, TrainingSystem, Variety
from app.modules.farms.models import Farm
from app.modules.registry.models import Block, IrrigationLayout, Planting, RecordVersion, Valve
from app.modules.soilwater.models import (
    IrrigationEvent,
    IrrigationSettings,
    SoilCheck,
    SoilProfile,
    WaterBalanceDaily,
)
from app.modules.weather.models import FarmThresholds, GddSetting, WeatherDaily, WeatherHourly

__all__ = [
    "AppUser",
    "Block",
    "Crop",
    "Farm",
    "FarmThresholds",
    "GddSetting",
    "IrrigationEvent",
    "IrrigationLayout",
    "IrrigationSettings",
    "Planting",
    "RecordVersion",
    "SoilCheck",
    "SoilProfile",
    "SoilTextureClass",
    "TrainingSystem",
    "Valve",
    "Variety",
    "WaterBalanceDaily",
    "WeatherDaily",
    "WeatherHourly",
]
