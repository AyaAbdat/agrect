"""Import every module's models here so Alembic autogenerate sees them."""

from app.jobs.models import JobRun
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
from app.modules.equipment.models import Machine, MachineUse, Maintenance
from app.modules.farms.models import Farm
from app.modules.harvest.models import HarvestEntry, HarvestQuality
from app.modules.inputs.models import CostLine, Price, StockMove
from app.modules.labour.models import Attendance, LabourLog, Worker
from app.modules.operations.models import (
    Operation,
    OperationProduct,
    OperationSafety,
    Product,
)
from app.modules.phenology.models import BlockSeason, StageObservation, StagePrediction
from app.modules.registry.models import Block, IrrigationLayout, Planting, RecordVersion, Valve
from app.modules.soilwater.models import (
    IrrigationEvent,
    IrrigationSettings,
    SoilCheck,
    SoilProfile,
    WaterBalanceDaily,
)
from app.modules.station.models import (
    CapacityDecision,
    Pump,
    PumpBlock,
    PumpWindow,
    Station,
    WaterSource,
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
    "Attendance",
    "Block",
    "BlockSeason",
    "CapacityDecision",
    "CostLine",
    "Crop",
    "CropScale",
    "Farm",
    "FarmStagePref",
    "FarmThresholds",
    "GddSetting",
    "GddSettingBlock",
    "HarvestEntry",
    "HarvestQuality",
    "HistoryDaily",
    "IrrigationEvent",
    "IrrigationLayout",
    "IrrigationSettings",
    "JobRun",
    "LabourLog",
    "Machine",
    "MachineUse",
    "Maintenance",
    "Operation",
    "OperationProduct",
    "OperationSafety",
    "Planting",
    "Price",
    "Product",
    "Pump",
    "PumpBlock",
    "PumpWindow",
    "RecordVersion",
    "SoilCheck",
    "SoilProfile",
    "SoilTextureClass",
    "StageDd",
    "StageDef",
    "Station",
    "StageObservation",
    "StagePrediction",
    "StockMove",
    "TrainingSystem",
    "Valve",
    "Variety",
    "VarietyChill",
    "WaterSource",
    "Worker",
    "WaterBalanceDaily",
    "WeatherDaily",
    "WeatherHourly",
]
