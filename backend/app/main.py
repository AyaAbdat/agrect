from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import farm_router as phenology_router
from app.modules.catalog.router import router as catalog_router
from app.modules.farms.router import router as farms_router
from app.modules.phenology.router import blocks_router as phenology_blocks_router
from app.modules.phenology.router import farm_router as phenology_summary_router
from app.modules.phenology.router import seasons_router as phenology_seasons_router
from app.modules.registry.block_router import blocks_router, farm_blocks_router
from app.modules.registry.router import router as registry_router
from app.modules.soilwater.router import calc_router as soilwater_calc_router
from app.modules.soilwater.router import farm_router as soilwater_farm_router
from app.modules.soilwater.router import router as soilwater_router
from app.modules.weather.router import blocks_router as weather_blocks_router
from app.modules.weather.router import router as weather_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AGRECT API",
        version="0.1.0",
        docs_url="/v1/docs",
        openapi_url="/v1/openapi.json",
        redoc_url=None,
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
    return app


app = create_app()
