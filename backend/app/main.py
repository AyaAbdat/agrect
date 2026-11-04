from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.health import router as health_router


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
    return app


app = create_app()
