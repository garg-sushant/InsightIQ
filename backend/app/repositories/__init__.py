"""Data access layer.

Everything tenant-owned goes through :class:`OrgScopedRepository`, which
guarantees ``organization_id`` filtering on reads and stamping on writes.
Services depend on these; routes never do.
"""

from app.repositories.ai_insight import AIInsightRepository
from app.repositories.analysis_run import AnalysisRunRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.base import BaseRepository, OrgScopedRepository
from app.repositories.customer import CustomerRepository
from app.repositories.dataset import DatasetRepository
from app.repositories.order import OrderRepository
from app.repositories.organization import OrganizationRepository
from app.repositories.product import ProductRepository
from app.repositories.return_order import ReturnRepository
from app.repositories.user import UserAuthRepository, UserRepository

__all__ = [
    "AIInsightRepository",
    "AnalysisRunRepository",
    "AuditLogRepository",
    "BaseRepository",
    "CustomerRepository",
    "DatasetRepository",
    "OrderRepository",
    "OrgScopedRepository",
    "OrganizationRepository",
    "ProductRepository",
    "ReturnRepository",
    "UserAuthRepository",
    "UserRepository",
]
