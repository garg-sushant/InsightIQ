"""FastAPI application entrypoint."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger, set_request_id
from app.db.session import dispose_engine
from app.schemas.common import HealthResponse
from app.services.ai.factory import provider_status

configure_logging(settings.log_level, json_output=settings.log_json)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("startup", extra={"environment": settings.environment})
    yield
    await dispose_engine()
    logger.info("shutdown")


app = FastAPI(
    title="InsightIQ API",
    version="1.0.0",
    description=(
        "AI Business Analytics & Decision Support Platform for retail sales data. "
        "Deterministic analytics plus AI narrative explaining why metrics moved "
        "and what to do next."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Stamp every request/response pair with a correlation id for log tracing."""
    incoming = request.headers.get("x-request-id")
    request_id = set_request_id(incoming if incoming else uuid.uuid4().hex[:16])
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Liveness/readiness probe. Never touches the AI provider on the hot path."""
    status_info = provider_status()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.environment,
        database="configured",
        ai_provider=f"{status_info.provider} ({'mock' if status_info.is_mock else 'live'})",
    )


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"name": "InsightIQ API", "docs": "/docs", "health": "/health"}
