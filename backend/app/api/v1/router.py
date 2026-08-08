"""Aggregates every v1 route module under a single APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.ai import router as ai_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.orgs import router as orgs_router
from app.api.v1.reports import router as reports_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(orgs_router)
api_router.include_router(datasets_router)
api_router.include_router(analytics_router)
api_router.include_router(ai_router)
api_router.include_router(reports_router)

__all__ = ["api_router"]
