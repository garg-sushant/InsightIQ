"""Shared response primitives: the error envelope, pagination, health."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for every request/response model in the API."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        extra="forbid",
    )


class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable explanation.")
    details: dict[str, Any] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """The single error shape returned by every endpoint."""

    error: ErrorDetail


class Message(APIModel):
    message: str


class PageMeta(APIModel):
    total: int
    limit: int
    offset: int
    has_more: bool


class Page(APIModel, Generic[T]):
    items: list[T]
    meta: PageMeta


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    ai_provider: str


__all__ = [
    "APIModel",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "Message",
    "Page",
    "PageMeta",
]
