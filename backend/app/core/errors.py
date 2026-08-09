"""Shared exception types and HTTP error handlers."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: str = "app_error", status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, code="not_found", status_code=404)


class ValidationAppError(AppError):
    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message=message, code="validation_error", status_code=422)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        payload: dict[str, Any] = {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        }
        return JSONResponse(status_code=exc.status_code, content=payload)
