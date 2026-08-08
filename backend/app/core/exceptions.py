"""Domain exceptions and the single, consistent HTTP error envelope.

Every error the API returns has the same shape::

    {
      "error": {
        "code": "not_found",
        "message": "Dataset not found.",
        "details": {...} | null,
        "request_id": "..."
      }
    }

Services raise :class:`AppError` subclasses; they never import ``fastapi`` or
raise ``HTTPException``. The translation to HTTP happens once, in the handlers
registered by :func:`register_exception_handlers`.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, get_request_id

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all expected, user-facing application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"
    message: str = "An application error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message or self.message
        self.details = details
        self.code = code or self.code
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "The requested resource was not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state of the resource."


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_error"
    message = "The submitted data failed validation."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_error"
    message = "Authentication credentials are missing or invalid."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    code = "payload_too_large"
    message = "The uploaded file is too large."


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    code = "unsupported_media_type"
    message = "The uploaded file type is not supported."


class IngestionError(AppError):
    """A dataset upload failed validation badly enough to reject the batch."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "ingestion_failed"
    message = "The dataset could not be ingested."


class AIProviderError(AppError):
    """The AI provider was unreachable or returned an unusable response.

    Callers are expected to degrade gracefully rather than surface a 5xx: the
    dashboard, analytics and exports all work without narrative.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "ai_provider_unavailable"
    message = "The AI provider is currently unavailable."


class InsufficientDataError(AppError):
    """Not enough rows to compute the requested analysis."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "insufficient_data"
    message = "There is not enough data to compute this analysis."


def _envelope(
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": get_request_id(),
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so every failure mode emits the same envelope."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("app_error", extra={"code": exc.code, "error_message": exc.message})
        else:
            logger.info("app_error", extra={"code": exc.code, "error_message": exc.message})
        headers = (
            {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic's error list contains non-JSON-native values (e.g. exception
        # instances under "ctx"); coerce to strings so the envelope serialises.
        issues = [
            {
                "location": ".".join(str(part) for part in error.get("loc", ())),
                "message": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error",
                "The submitted data failed validation.",
                {"issues": issues},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        _: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = {
            401: "authentication_error",
            403: "permission_denied",
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limited",
        }.get(exc.status_code, "http_error")
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"error_type": type(exc).__name__})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "internal_error",
                "An unexpected error occurred. The incident has been logged.",
            ),
        )


__all__ = [
    "AIProviderError",
    "AppError",
    "AuthenticationError",
    "ConflictError",
    "IngestionError",
    "InsufficientDataError",
    "NotFoundError",
    "PayloadTooLargeError",
    "PermissionDeniedError",
    "UnsupportedMediaTypeError",
    "ValidationError",
    "register_exception_handlers",
]
