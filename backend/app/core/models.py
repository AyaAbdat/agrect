"""Import every module's models here so Alembic autogenerate sees them."""

from app.modules.auth.models import AppUser
from app.modules.catalog.models import (
    Crop,
    CropScale,
    FarmStagePref,
    SoilTextureClass,
    StageDd,
    StageDef,
    TrainingSystem,
    Variety,
    VarietyChill,
)
from app.modules.farms.models import Farm
from app.modules.phenology.models import BlockSeason, StageObservation, StagePrediction
from app.modules.registry.models import Block, IrrigationLayout, Planting, RecordVersion, Valve
from app.modules.soilwater.models import (
    IrrigationEvent,
    IrrigationSettings,
    SoilCheck,
    SoilProfile,
    WaterBalanceDaily,
)
from app.modules.weather.models import (
    FarmThresholds,
    GddSetting,
    GddSettingBlock,
    HistoryDaily,
    WeatherDaily,
    WeatherHourly,
)

__all__ = [
    "AppUser",
    "Block",
    "BlockSeason",
    "Crop",
    "CropScale",
    "Farm",
    "FarmStagePref",
    "FarmThresholds",
    "GddSetting",
    "GddSettingBlock",
    "HistoryDaily",
    "IrrigationEvent",
    "IrrigationLayout",
    "IrrigationSettings",
    "Planting",
    "RecordVersion",
    "SoilCheck",
    "SoilProfile",
    "SoilTextureClass",
    "StageDd",
    "StageDef",
    "StageObservation",
    "StagePrediction",
    "TrainingSystem",
    "Valve",
    "Variety",
    "VarietyChill",
    "WaterBalanceDaily",
    "WeatherDaily",
    "WeatherHourly",
]
