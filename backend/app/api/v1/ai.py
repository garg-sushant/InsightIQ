"""AI narrative endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import CurrentAuth, DbSession, require
from app.core.exceptions import NotFoundError
from app.core.security import Permission
from app.schemas.ai import AIPayload, AIStatusOut, GenerateInsightsRequest, InsightBundle
from app.services.ai.factory import provider_status
from app.services.ai.service import AIService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/status", response_model=AIStatusOut, summary="Which AI provider is active")
async def get_status() -> AIStatusOut:
    return provider_status()


@router.post(
    "/generate",
    response_model=InsightBundle,
    dependencies=[require(Permission.AI_GENERATE)],
    summary="Generate (or return cached) narrative for an analysis run",
)
async def generate_insights(
    payload: GenerateInsightsRequest, auth: CurrentAuth, session: DbSession
) -> InsightBundle:
    service = AIService(session, auth.organization_id)
    return await service.generate(payload.analysis_run_id, refresh=payload.refresh)


@router.get(
    "/insights/{run_id}",
    response_model=InsightBundle,
    dependencies=[require(Permission.ANALYTICS_READ)],
    summary="Previously generated narrative for a run, if any",
)
async def get_insights(
    run_id: uuid.UUID, auth: CurrentAuth, session: DbSession
) -> InsightBundle:
    service = AIService(session, auth.organization_id)
    bundle = await service.get_bundle(run_id)
    if bundle is None:
        raise NotFoundError("No AI narrative has been generated for this run yet.")
    return bundle


@router.get(
    "/payload/{run_id}",
    response_model=AIPayload,
    dependencies=[require(Permission.ANALYTICS_READ)],
    summary="Transparency: the exact sanitised payload sent to the AI provider",
)
async def get_payload(
    run_id: uuid.UUID, auth: CurrentAuth, session: DbSession
) -> AIPayload:
    service = AIService(session, auth.organization_id)
    return await service.build_payload_for_run(run_id)
