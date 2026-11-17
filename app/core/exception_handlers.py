import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def error_response(
    status_code: int,
    message: str,
    *,
    errors: list | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content=jsonable_encoder(
            {
                "success": False,
                "message": message,
                "data": None,
                "errors": errors or [],
            }
        ),
    )


async def app_error_handler(
    request: Request,
    exc: AppError,
) -> JSONResponse:
    return error_response(
        exc.status_code,
        exc.message,
        headers=exc.headers,
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    return error_response(
        exc.status_code,
        exc.detail if isinstance(exc.detail, str) else "Error HTTP.",
        errors=[] if isinstance(exc.detail, str) else [exc.detail],
        headers=exc.headers,
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    # No devolvemos "input": podría contener contraseñas.
    errors = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]

    return error_response(
        422,
        "Los datos enviados no son válidos.",
        errors=errors,
    )


async def unexpected_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.error(
        "Error inesperado en %s %s",
        request.method,
        request.url.path,
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return error_response(
        500,
        "Ocurrió un error interno.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(
        StarletteHTTPException,
        http_error_handler,
    )
    app.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )
    app.add_exception_handler(Exception, unexpected_error_handler)
