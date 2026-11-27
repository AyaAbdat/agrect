from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.health import router as health_router
from app.jobs.router import farm_router as jobs_farm_router
from app.jobs.scheduler import start_jobs_if_enabled, stop_scheduler
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import farm_router as phenology_router
from app.modules.catalog.router import router as catalog_router
from app.modules.compare.router import farm_router as compare_farm_router
from app.modules.equipment.router import farm_router as equipment_farm_router
from app.modules.equipment.router import machine_router as equipment_machine_router
from app.modules.equipment.router import maintenance_router as equipment_maintenance_router
from app.modules.farms.router import router as farms_router
from app.modules.harvest.router import calc_router as harvest_calc_router
from app.modules.harvest.router import catalog_router as harvest_catalog_router
from app.modules.harvest.router import farm_router as harvest_farm_router
from app.modules.harvest.router import router as harvest_router
from app.modules.inputs.router import blocks_router as inputs_blocks_router
from app.modules.inputs.router import farm_router as inputs_farm_router
from app.modules.inputs.router import price_router as inputs_price_router
from app.modules.inputs.router import stock_move_router as inputs_stock_move_router
from app.modules.labour.router import farm_router as labour_farm_router
from app.modules.labour.router import worker_router as labour_worker_router
from app.modules.operations.router import blocks_router as operations_blocks_router
from app.modules.operations.router import calc_router as operations_calc_router
from app.modules.operations.router import farm_router as operations_farm_router
from app.modules.operations.router import operation_router as operations_item_router
from app.modules.operations.router import product_router as operations_product_router
from app.modules.phenology.router import blocks_router as phenology_blocks_router
from app.modules.phenology.router import farm_router as phenology_summary_router
from app.modules.phenology.router import seasons_router as phenology_seasons_router
from app.modules.registry.block_router import blocks_router, farm_blocks_router
from app.modules.registry.router import router as registry_router
from app.modules.soilwater.router import calc_router as soilwater_calc_router
from app.modules.soilwater.router import farm_router as soilwater_farm_router
from app.modules.soilwater.router import router as soilwater_router
from app.modules.station.router import farm_router as station_farm_router
from app.modules.station.router import pump_router as station_pump_router
from app.modules.station.router import source_router as station_source_router
from app.modules.timeline.router import farm_router as timeline_farm_router
from app.modules.weather.router import blocks_router as weather_blocks_router
from app.modules.weather.router import router as weather_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start background jobs only when JOBS_ENABLED is true (D-084)."""
    handle = start_jobs_if_enabled(get_settings())
    app.state.scheduler = handle
    try:
        yield
    finally:
        if handle is not None:
            stop_scheduler(handle)
        app.state.scheduler = None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AGRECT API",
        version="0.1.0",
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.include_router(health_router, prefix="/v1")
    app.include_router(auth_router, prefix="/v1")
    app.include_router(farms_router, prefix="/v1")
    app.include_router(catalog_router, prefix="/v1")
    app.include_router(phenology_router, prefix="/v1")
    app.include_router(phenology_blocks_router, prefix="/v1")
    app.include_router(phenology_seasons_router, prefix="/v1")
    app.include_router(phenology_summary_router, prefix="/v1")
    app.include_router(registry_router, prefix="/v1")
    app.include_router(farm_blocks_router, prefix="/v1")
    app.include_router(blocks_router, prefix="/v1")
    app.include_router(soilwater_router, prefix="/v1")
    app.include_router(soilwater_farm_router, prefix="/v1")
    app.include_router(soilwater_calc_router, prefix="/v1")
    app.include_router(weather_router, prefix="/v1")
    app.include_router(weather_blocks_router, prefix="/v1")
    app.include_router(station_farm_router, prefix="/v1")
    app.include_router(station_pump_router, prefix="/v1")
    app.include_router(station_source_router, prefix="/v1")
    app.include_router(harvest_router, prefix="/v1")
    app.include_router(harvest_farm_router, prefix="/v1")
    app.include_router(harvest_catalog_router, prefix="/v1")
    app.include_router(harvest_calc_router, prefix="/v1")
    app.include_router(operations_farm_router, prefix="/v1")
    app.include_router(operations_product_router, prefix="/v1")
    app.include_router(operations_item_router, prefix="/v1")
    app.include_router(operations_blocks_router, prefix="/v1")
    app.include_router(operations_calc_router, prefix="/v1")
    app.include_router(inputs_farm_router, prefix="/v1")
    app.include_router(inputs_price_router, prefix="/v1")
    app.include_router(inputs_stock_move_router, prefix="/v1")
    app.include_router(inputs_blocks_router, prefix="/v1")
    app.include_router(labour_farm_router, prefix="/v1")
    app.include_router(labour_worker_router, prefix="/v1")
    app.include_router(equipment_farm_router, prefix="/v1")
    app.include_router(equipment_machine_router, prefix="/v1")
    app.include_router(equipment_maintenance_router, prefix="/v1")
    app.include_router(jobs_farm_router, prefix="/v1")
    app.include_router(compare_farm_router, prefix="/v1")
    app.include_router(timeline_farm_router, prefix="/v1")
    return app


app = create_app()
