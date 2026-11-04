from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine

router = APIRouter()

APP_VERSION = "0.1.0"


class HealthOut(BaseModel):
    status: str
    db: str
    postgis: str | None
    version: str


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut | JSONResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            postgis = connection.execute(text("SELECT postgis_lib_version()")).scalar_one()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "db": "down",
                "postgis": None,
                "version": APP_VERSION,
            },
        )
    return HealthOut(status="ok", db="ok", postgis=str(postgis), version=APP_VERSION)
