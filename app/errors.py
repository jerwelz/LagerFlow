"""Application errors and the handlers that turn them into consistent JSON responses.

Every error response has the same shape:
    {"error": {"code": "...", "message": "...", "details": ...}}
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str = Field(examples=["PRODUCT_NOT_FOUND"])
    message: str = Field(examples=["Product 42 not found."])
    details: Any = None


class ErrorResponse(BaseModel):
    """The body of every error response. Used to document errors in /docs."""

    error: ErrorDetail


_ERROR_DESCRIPTIONS = {
    404: "The product does not exist.",
    409: "The request conflicts with the current state "
    "(e.g. duplicate SKU, insufficient stock, inactive product).",
    422: "The request is invalid (wrong type, out of range, unknown field, ...).",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses` entries for the given error status codes.

    Declaring 422 here also replaces FastAPI's default 422 schema, which does
    not match our error format.
    """
    return {
        code: {"model": ErrorResponse, "description": _ERROR_DESCRIPTIONS[code]}
        for code in status_codes
    }


class AppError(Exception):
    """Base class for errors raised by the service layer."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class ConflictError(AppError):
    """The request is valid, but conflicts with the current state (e.g. duplicate SKU)."""

    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


def error_response(status_code: int, code: str, message: str, details: Any = None) -> JSONResponse:
    body = {"error": {"code": code, "message": message, "details": details}}
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
    return error_response(exc.status_code, exc.code, exc.message, exc.details)


async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "Request validation failed.",
        exc.errors(),
    )


async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Covers framework errors such as unknown routes (404) or wrong methods (405).
    return error_response(exc.status_code, "HTTP_ERROR", str(exc.detail))


async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error", exc_info=exc)
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "An unexpected error occurred."
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, handle_app_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)
