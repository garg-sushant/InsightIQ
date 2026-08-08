"""Ingestion orchestration: parse -> validate -> persist, atomically per batch.

Transaction shape matters here. The ``Dataset`` audit record must survive even
when the batch is rejected, so a failed ingest commits *only* the dataset row
(with its validation report) and never any facts. A successful ingest commits
facts and dataset row together.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import IngestionError
from app.core.logging import get_logger
from app.models.dataset import Dataset, DatasetStatus, EntityType
from app.repositories.audit_log import AuditLogRepository
from app.repositories.customer import CustomerRepository
from app.repositories.dataset import DatasetRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.return_order import ReturnRepository
from app.schemas.dataset import ValidationReport
from app.services.ingestion.parser import parse_upload
from app.services.ingestion.spec import get_spec
from app.services.ingestion.validators import (
    ROW_NUMBER,
    ErrorCollector,
    ValidationOutcome,
    check_references,
    validate_frame,
)

logger = get_logger(__name__)

#: Rows per executemany batch. Large enough to be fast, small enough that a
#: single statement never exceeds Postgres' parameter limits.
INSERT_CHUNK = 2_000


class IngestionService:
    def __init__(self, session: AsyncSession, organization_id: uuid.UUID) -> None:
        self.session = session
        self.organization_id = organization_id
        self.datasets = DatasetRepository(session, organization_id)
        self.customers = CustomerRepository(session, organization_id)
        self.products = ProductRepository(session, organization_id)
        self.orders = OrderRepository(session, organization_id)
        self.returns = ReturnRepository(session, organization_id)
        self.audit = AuditLogRepository(session, organization_id)

    async def ingest(
        self,
        *,
        entity_type: EntityType,
        filename: str,
        content: bytes,
        content_type: str | None = None,
        user_id: uuid.UUID | None = None,
        actor_email: str | None = None,
    ) -> tuple[Dataset, ValidationReport]:
        started = time.perf_counter()
        spec = get_spec(entity_type)

        # Parse first: a structurally unusable file never becomes a Dataset row.
        parsed = parse_upload(filename, content)

        dataset = Dataset(
            entity_type=entity_type,
            status=DatasetStatus.VALIDATING,
            original_filename=filename[:400],
            content_type=(content_type or "")[:160] or None,
            file_size_bytes=parsed.size_bytes,
            checksum_sha256=parsed.checksum_sha256,
            rows_total=len(parsed.frame),
            uploaded_by_user_id=user_id,
        )
        await self.datasets.add(dataset)

        outcome = validate_frame(parsed.frame, spec)
        collector = ErrorCollector()
        collector.errors = list(outcome.errors)
        collector.counts = dict(outcome.error_counts)
        collector.truncated = outcome.errors_truncated

        if outcome.is_valid:
            try:
                await self._resolve_references(entity_type, outcome, collector)
            except IngestionError as exc:
                outcome.critical_error = exc.message

        report = self._build_report(entity_type, outcome, collector)

        if not outcome.is_valid:
            return await self._fail(dataset, report, outcome, started, user_id, actor_email)

        try:
            written = await self._persist(entity_type, outcome.frame, dataset.id)
        except IntegrityError as exc:
            await self.session.rollback()
            logger.warning("ingest_integrity_error", extra={"error": str(exc.orig)})
            # The dataset row was rolled back with everything else; re-create it
            # so the user still sees a record of the failed attempt.
            return await self._record_failed_attempt(
                entity_type=entity_type,
                filename=filename,
                content_type=content_type,
                parsed_size=parsed.size_bytes,
                checksum=parsed.checksum_sha256,
                rows_total=outcome.rows_total,
                user_id=user_id,
                actor_email=actor_email,
                message=(
                    "The batch conflicted with existing data and was rejected "
                    "atomically. No rows were imported."
                ),
                report=report,
                started=started,
            )

        dataset.status = (
            DatasetStatus.PARTIAL if outcome.rows_rejected else DatasetStatus.INGESTED
        )
        dataset.rows_accepted = written
        dataset.rows_rejected = outcome.rows_total - written
        dataset.validation_report = report.model_dump(mode="json")
        dataset.completed_at = datetime.now(UTC)
        dataset.duration_ms = int((time.perf_counter() - started) * 1000)

        await self.audit.record(
            action="dataset.upload",
            resource_type="dataset",
            resource_id=str(dataset.id),
            user_id=user_id,
            actor_email=actor_email,
            context={
                "entity_type": entity_type.value,
                "rows_accepted": written,
                "rows_rejected": dataset.rows_rejected,
            },
        )
        await self.session.commit()
        logger.info(
            "ingest_complete",
            extra={
                "entity_type": entity_type.value,
                "rows_accepted": written,
                "rows_rejected": dataset.rows_rejected,
            },
        )
        return dataset, report

    # -- failure paths ------------------------------------------------------
    async def _fail(
        self,
        dataset: Dataset,
        report: ValidationReport,
        outcome: ValidationOutcome,
        started: float,
        user_id: uuid.UUID | None,
        actor_email: str | None,
    ) -> tuple[Dataset, ValidationReport]:
        dataset.status = DatasetStatus.FAILED
        dataset.rows_accepted = 0
        dataset.rows_rejected = outcome.rows_total
        dataset.error_message = outcome.critical_error
        dataset.validation_report = report.model_dump(mode="json")
        dataset.completed_at = datetime.now(UTC)
        dataset.duration_ms = int((time.perf_counter() - started) * 1000)

        await self.audit.record(
            action="dataset.upload_rejected",
            resource_type="dataset",
            resource_id=str(dataset.id),
            user_id=user_id,
            actor_email=actor_email,
            context={"reason": (outcome.critical_error or "")[:300]},
        )
        await self.session.commit()
        logger.info("ingest_rejected", extra={"reason": outcome.critical_error})
        return dataset, report

    async def _record_failed_attempt(
        self,
        *,
        entity_type: EntityType,
        filename: str,
        content_type: str | None,
        parsed_size: int,
        checksum: str,
        rows_total: int,
        user_id: uuid.UUID | None,
        actor_email: str | None,
        message: str,
        report: ValidationReport,
        started: float,
    ) -> tuple[Dataset, ValidationReport]:
        report = report.model_copy(update={"is_valid": False, "rows_accepted": 0,
                                           "rows_rejected": rows_total})
        dataset = Dataset(
            entity_type=entity_type,
            status=DatasetStatus.FAILED,
            original_filename=filename[:400],
            content_type=(content_type or "")[:160] or None,
            file_size_bytes=parsed_size,
            checksum_sha256=checksum,
            rows_total=rows_total,
            rows_accepted=0,
            rows_rejected=rows_total,
            uploaded_by_user_id=user_id,
            error_message=message,
            validation_report=report.model_dump(mode="json"),
            completed_at=datetime.now(UTC),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        await self.datasets.add(dataset)
        await self.audit.record(
            action="dataset.upload_rejected",
            resource_type="dataset",
            resource_id=str(dataset.id),
            user_id=user_id,
            actor_email=actor_email,
            context={"reason": message[:300]},
        )
        await self.session.commit()
        return dataset, report

    # -- referential integrity ---------------------------------------------
    async def _resolve_references(
        self,
        entity_type: EntityType,
        outcome: ValidationOutcome,
        collector: ErrorCollector,
    ) -> None:
        """Check and, where possible, satisfy cross-entity references."""
        frame = outcome.frame
        if frame.empty:
            return

        if entity_type is EntityType.RETURNS:
            known_orders = await self.orders.existing_order_refs()
            unknown = check_references(
                frame,
                "order_ref",
                known_orders,
                error_type="unknown_order",
                message="No order with this reference exists. Upload orders first.",
                collector=collector,
            )
            count = int(unknown.sum())
            if count:
                outcome.referential_issues["returns_without_matching_order"] = count
                outcome.frame = frame[~unknown]
                outcome.rows_accepted = len(outcome.frame)
                outcome.rows_rejected = outcome.rows_total - outcome.rows_accepted
                if outcome.rows_accepted == 0:
                    raise IngestionError(
                        "None of the returned orders exist in this workspace. "
                        "Upload the orders file first. No rows were imported."
                    )
            return

        if entity_type is EntityType.ORDERS:
            await self._autocreate_masters(outcome, collector)

    async def _autocreate_masters(
        self, outcome: ValidationOutcome, collector: ErrorCollector
    ) -> None:
        """Create Customer/Product rows implied by an orders file.

        The canonical Superstore export carries customer and product attributes
        inline, so requiring three uploads before any order can land would be
        hostile. A row is only rejected when the reference is unknown *and* the
        file carries no name to create the master record from.
        """
        frame = outcome.frame

        for kind, ref_column, name_column in (
            ("customer", "customer_ref", "customer_name"),
            ("product", "product_ref", "product_name"),
        ):
            refs = [r for r in frame[ref_column].dropna().unique().tolist()]
            existing = (
                await self.customers.existing_refs(refs)
                if kind == "customer"
                else await self.products.existing_refs(refs)
            )
            missing = [r for r in refs if r not in existing]
            if not missing:
                continue

            creatable: list[str] = []
            uncreatable: list[str] = []
            for ref in missing:
                rows = frame[frame[ref_column] == ref]
                names = rows[name_column].dropna() if name_column in rows else pd.Series(
                    dtype=object
                )
                (creatable if len(names) else uncreatable).append(ref)

            if uncreatable:
                unknown = frame[ref_column].isin(uncreatable)
                for index in frame.index[unknown]:
                    collector.add(
                        row_number=int(frame.at[index, ROW_NUMBER]),
                        column=ref_column,
                        error_type=f"unknown_{kind}",
                        message=(
                            f"No {kind} with this reference exists and the file "
                            f"has no '{name_column}' to create one from."
                        ),
                        value=frame.at[index, ref_column],
                    )
                outcome.referential_issues[f"orders_with_unknown_{kind}"] = int(unknown.sum())
                frame = frame[~unknown]
                outcome.frame = frame

            if creatable:
                await self._create_masters(kind, frame, creatable)
                outcome.warnings.append(
                    f"{len(creatable)} new {kind} record(s) were created from this file."
                )

        outcome.rows_accepted = len(outcome.frame)
        outcome.rows_rejected = outcome.rows_total - outcome.rows_accepted
        if outcome.rows_accepted == 0:
            raise IngestionError(
                "No rows could be linked to a customer and product. "
                "No rows were imported."
            )

    async def _create_masters(self, kind: str, frame: pd.DataFrame, refs: list[str]) -> None:
        """Insert master rows using the first non-null attribute set per reference."""
        subset = frame[frame[f"{kind}_ref"].isin(refs)]
        # ``first`` skips NaN, so a row missing region still contributes its name.
        grouped = subset.groupby(f"{kind}_ref", sort=False, dropna=True)

        rows: list[dict[str, Any]] = []
        if kind == "customer":
            for ref, group in grouped:
                rows.append(
                    {
                        "customer_ref": str(ref),
                        "name": _first(group, "customer_name") or str(ref),
                        "segment": _first(group, "segment"),
                        "country": _first(group, "country"),
                        "region": _first(group, "region"),
                        "state": _first(group, "state"),
                        "city": _first(group, "city"),
                        "postal_code": _first(group, "postal_code"),
                    }
                )
            await self.customers.bulk_insert_mappings(rows)
        else:
            for ref, group in grouped:
                rows.append(
                    {
                        "product_ref": str(ref),
                        "name": _first(group, "product_name") or str(ref),
                        "category": _first(group, "category"),
                        "sub_category": _first(group, "sub_category"),
                        "unit_price": _first_decimal(group, "unit_price"),
                    }
                )
            await self.products.bulk_insert_mappings(rows)

    # -- persistence --------------------------------------------------------
    async def _persist(
        self, entity_type: EntityType, frame: pd.DataFrame, dataset_id: uuid.UUID
    ) -> int:
        if frame.empty:
            return 0
        builder = {
            EntityType.ORDERS: self._build_order_rows,
            EntityType.CUSTOMERS: self._build_customer_rows,
            EntityType.PRODUCTS: self._build_product_rows,
            EntityType.RETURNS: self._build_return_rows,
        }[entity_type]
        rows = await builder(frame, dataset_id)
        if not rows:
            return 0

        repository = {
            EntityType.ORDERS: self.orders,
            EntityType.CUSTOMERS: self.customers,
            EntityType.PRODUCTS: self.products,
            EntityType.RETURNS: self.returns,
        }[entity_type]

        written = 0
        for start in range(0, len(rows), INSERT_CHUNK):
            chunk = rows[start : start + INSERT_CHUNK]
            written += await repository.bulk_insert_mappings(chunk)
        return written

    async def _build_order_rows(
        self, frame: pd.DataFrame, dataset_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        customer_ids = await self.customers.ref_to_id_map()
        product_ids = await self.products.ref_to_id_map()

        # Re-uploading the same file must not duplicate lines.
        line_refs = _generated_line_refs(frame)
        already = await self.orders.existing_line_refs(line_refs.tolist())

        rows: list[dict[str, Any]] = []
        for position, (_, record) in enumerate(frame.iterrows()):
            line_ref = line_refs.iloc[position]
            if line_ref in already:
                continue
            customer_id = customer_ids.get(str(record["customer_ref"]))
            product_id = product_ids.get(str(record["product_ref"]))
            if customer_id is None or product_id is None:
                continue

            quantity = _as_int(record.get("quantity"))
            sales = _as_decimal(record.get("sales"))
            unit_price = _as_decimal(record.get("unit_price"))
            if unit_price is None:
                # Realised net price per unit. Guarded against zero quantity.
                unit_price = (sales / quantity) if (sales is not None and quantity) else Decimal(0)

            rows.append(
                {
                    "line_ref": str(line_ref),
                    "order_ref": str(record["order_ref"]),
                    "order_date": record["order_date"],
                    "ship_date": _as_date(record.get("ship_date")),
                    "ship_mode": _as_str(record.get("ship_mode")),
                    "customer_id": customer_id,
                    "product_id": product_id,
                    "region": _as_str(record.get("region")),
                    "country": _as_str(record.get("country")),
                    "state": _as_str(record.get("state")),
                    "city": _as_str(record.get("city")),
                    "segment": _as_str(record.get("segment")),
                    "category": _as_str(record.get("category")),
                    "sub_category": _as_str(record.get("sub_category")),
                    "quantity": quantity,
                    "unit_price": _quantize(unit_price),
                    "discount": _quantize(_as_decimal(record.get("discount")) or Decimal(0), 6),
                    "sales": _quantize(sales or Decimal(0)),
                    "profit": _quantize(_as_decimal(record.get("profit")) or Decimal(0)),
                    "dataset_id": dataset_id,
                }
            )
        return rows

    async def _build_customer_rows(
        self, frame: pd.DataFrame, dataset_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        existing = await self.customers.existing_refs(
            frame["customer_ref"].dropna().astype(str).tolist()
        )
        rows: list[dict[str, Any]] = []
        for _, record in frame.iterrows():
            ref = str(record["customer_ref"])
            if ref in existing:
                continue
            rows.append(
                {
                    "customer_ref": ref,
                    "name": _as_str(record.get("name")) or ref,
                    "segment": _as_str(record.get("segment")),
                    "country": _as_str(record.get("country")),
                    "region": _as_str(record.get("region")),
                    "state": _as_str(record.get("state")),
                    "city": _as_str(record.get("city")),
                    "postal_code": _as_str(record.get("postal_code")),
                    "dataset_id": dataset_id,
                }
            )
        return rows

    async def _build_product_rows(
        self, frame: pd.DataFrame, dataset_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        existing = await self.products.existing_refs(
            frame["product_ref"].dropna().astype(str).tolist()
        )
        rows: list[dict[str, Any]] = []
        for _, record in frame.iterrows():
            ref = str(record["product_ref"])
            if ref in existing:
                continue
            price = _as_decimal(record.get("unit_price"))
            rows.append(
                {
                    "product_ref": ref,
                    "name": _as_str(record.get("name")) or ref,
                    "category": _as_str(record.get("category")),
                    "sub_category": _as_str(record.get("sub_category")),
                    "unit_price": _quantize(price) if price is not None else None,
                    "dataset_id": dataset_id,
                }
            )
        return rows

    async def _build_return_rows(
        self, frame: pd.DataFrame, dataset_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        existing = await self.returns.existing_order_refs(
            frame["order_ref"].dropna().astype(str).tolist()
        )
        rows: list[dict[str, Any]] = []
        for _, record in frame.iterrows():
            ref = str(record["order_ref"])
            if ref in existing:
                continue
            returned = record.get("returned")
            rows.append(
                {
                    "order_ref": ref,
                    "returned": True if returned is None or pd.isna(returned) else bool(returned),
                    "return_date": _as_date(record.get("return_date")),
                    "reason": _as_str(record.get("reason")),
                    "dataset_id": dataset_id,
                }
            )
        return rows

    # -- reporting ----------------------------------------------------------
    @staticmethod
    def _build_report(
        entity_type: EntityType,
        outcome: ValidationOutcome,
        collector: ErrorCollector,
    ) -> ValidationReport:
        return ValidationReport(
            entity_type=entity_type,
            is_valid=outcome.is_valid,
            rows_total=outcome.rows_total,
            rows_accepted=outcome.rows_accepted if outcome.is_valid else 0,
            rows_rejected=(
                outcome.rows_rejected if outcome.is_valid else outcome.rows_total
            ),
            duplicate_keys_dropped=outcome.duplicates_dropped,
            missing_required_columns=outcome.missing_required_columns,
            unexpected_columns=outcome.unexpected_columns,
            columns=outcome.columns,
            errors=collector.errors,
            error_counts=collector.counts,
            errors_truncated=collector.truncated,
            warnings=(
                [*outcome.warnings, outcome.critical_error]
                if outcome.critical_error
                else outcome.warnings
            ),
            referential_issues=outcome.referential_issues,
        )


# ---------------------------------------------------------------------------
# Cell conversion helpers
# ---------------------------------------------------------------------------
def _generated_line_refs(frame: pd.DataFrame) -> pd.Series:
    """Use the file's own line id when present; otherwise derive a stable one."""
    derived = (
        frame["order_ref"].astype(str)
        + "::"
        + frame["product_ref"].astype(str)
        + "::"
        + frame[ROW_NUMBER].astype(str)
    )
    if "line_ref" not in frame.columns:
        return derived
    supplied = frame["line_ref"]
    return supplied.where(supplied.notna(), derived).astype(str)


def _first(group: pd.DataFrame, column: str) -> str | None:
    if column not in group.columns:
        return None
    values = group[column].dropna()
    return str(values.iloc[0]) if len(values) else None


def _first_decimal(group: pd.DataFrame, column: str) -> Decimal | None:
    if column not in group.columns:
        return None
    values = group[column].dropna()
    return _quantize(_as_decimal(values.iloc[0])) if len(values) else None


def _as_str(value: object) -> str | None:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: object) -> int:
    if value is None or pd.isna(value):
        return 0
    return int(value)  # type: ignore[arg-type]


def _as_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    try:
        return Decimal(str(value))
    except (ValueError, ArithmeticError):
        return None


def _as_date(value: object) -> object | None:
    if value is None or value is pd.NaT:
        return None
    try:
        if pd.isna(value):  # type: ignore[arg-type]
            return None
    except (TypeError, ValueError):
        pass
    return value


def _quantize(value: Decimal | None, places: int = 4) -> Decimal:
    if value is None:
        return Decimal(0).quantize(Decimal(10) ** -places)
    return value.quantize(Decimal(10) ** -places)


__all__ = ["INSERT_CHUNK", "IngestionService"]
