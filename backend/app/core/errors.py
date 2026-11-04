import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        status_code: int = 400,
        fields: dict[str, str] | None = None,
    ) -> None:
        self.code = code
        self.status_code = status_code
        self.fields = fields
        super().__init__(code)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "fields": exc.fields or {}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        fields: dict[str, str] = {}
        for error in exc.errors():
            loc = ".".join(str(part) for part in error["loc"])
            fields[loc] = str(error["type"])
        return JSONResponse(
            status_code=422,
            content={"code": "validation_error", "fields": fields},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        if exc.status_code == 404:
            return JSONResponse(status_code=404, content={"code": "not_found"})
        return JSONResponse(status_code=exc.status_code, content={"code": "http_error"})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content={"code": "internal_error"})
