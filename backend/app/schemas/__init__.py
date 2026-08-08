"""Pydantic request/response models. Every endpoint uses one on both sides."""

from app.schemas.common import (
    APIModel,
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    Message,
    Page,
    PageMeta,
)

__all__ = [
    "APIModel",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "Message",
    "Page",
    "PageMeta",
]
