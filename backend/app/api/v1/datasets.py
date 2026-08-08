"""Dataset upload and inventory endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Query, UploadFile, status

from app.core.deps import CurrentAuth, DbSession, client_ip, require, user_agent
from app.core.exceptions import NotFoundError
from app.core.security import Permission
from app.models.dataset import DatasetStatus, EntityType
from app.repositories.dataset import DatasetRepository
from app.schemas.common import Page, PageMeta
from app.schemas.dataset import (
    DataInventoryOut,
    DatasetDetailOut,
    DatasetOut,
    EntitySchemaColumn,
    EntitySchemaOut,
    UploadResponse,
)
from app.services.analytics.service import AnalyticsService
from app.services.ingestion.service import IngestionService
from app.services.ingestion.spec import get_spec

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("/schema/{entity_type}", response_model=EntitySchemaOut, summary="Expected upload shape")
async def get_schema(entity_type: EntityType) -> EntitySchemaOut:
    spec = get_spec(entity_type)
    return EntitySchemaOut(
        entity_type=entity_type,
        primary_key=list(spec.primary_key),
        columns=[
            EntitySchemaColumn(
                name=column.name,
                required=column.required,
                data_type=column.field_type.value,
                description=column.description,
                aliases=list(column.aliases),
            )
            for column in spec.columns
        ],
    )


@router.get("/inventory", response_model=DataInventoryOut, summary="Row counts per entity")
async def get_inventory(auth: CurrentAuth, session: DbSession) -> DataInventoryOut:
    service = AnalyticsService(session, auth.organization_id)
    return await service.inventory()


@router.post(
    "/upload/{entity_type}",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require(Permission.DATASET_WRITE)],
    summary="Upload a CSV/XLSX file for one entity type",
)
async def upload_dataset(
    entity_type: EntityType,
    auth: CurrentAuth,
    session: DbSession,
    file: UploadFile = File(...),
) -> UploadResponse:
    content = await file.read()
    service = IngestionService(session, auth.organization_id)
    dataset, report = await service.ingest(
        entity_type=entity_type,
        filename=file.filename or "upload",
        content=content,
        content_type=file.content_type,
        user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    return UploadResponse(dataset=DatasetOut.model_validate(dataset), report=report)


@router.get(
    "",
    response_model=Page[DatasetOut],
    dependencies=[require(Permission.DATASET_READ)],
    summary="List uploaded datasets",
)
async def list_datasets(
    auth: CurrentAuth,
    session: DbSession,
    entity_type: EntityType | None = Query(default=None),
    status_filter: DatasetStatus | None = Query(default=None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Page[DatasetOut]:
    repository = DatasetRepository(session, auth.organization_id)
    items = await repository.list_for_org(
        entity_type=entity_type, status=status_filter, limit=limit, offset=offset
    )
    total = await repository.count_for_org(entity_type=entity_type, status=status_filter)
    return Page[DatasetOut](
        items=[DatasetOut.model_validate(item) for item in items],
        meta=PageMeta(total=total, limit=limit, offset=offset, has_more=offset + len(items) < total),
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetailOut,
    dependencies=[require(Permission.DATASET_READ)],
    summary="Dataset detail with full validation report",
)
async def get_dataset(
    dataset_id: uuid.UUID, auth: CurrentAuth, session: DbSession
) -> DatasetDetailOut:
    repository = DatasetRepository(session, auth.organization_id)
    dataset = await repository.get(dataset_id)
    if dataset is None:
        raise NotFoundError("Dataset not found.")
    return DatasetDetailOut.model_validate(dataset)
