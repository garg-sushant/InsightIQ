"""SQLAlchemy models.

Importing this package registers every table on ``Base.metadata`` — Alembic's
autogenerate and the test-suite schema creation both rely on that.
"""

from app.models.ai_insight import AIInsight, InsightType
from app.models.analysis_run import AnalysisRun, AnalysisStatus
from app.models.audit_log import AuditLog
from app.models.base import Base
from app.models.customer import Customer
from app.models.dataset import Dataset, DatasetStatus, EntityType
from app.models.order import Order
from app.models.organization import Organization
from app.models.product import Product
from app.models.return_order import Return
from app.models.user import User

__all__ = [
    "AIInsight",
    "AnalysisRun",
    "AnalysisStatus",
    "AuditLog",
    "Base",
    "Customer",
    "Dataset",
    "DatasetStatus",
    "EntityType",
    "InsightType",
    "Order",
    "Organization",
    "Product",
    "Return",
    "User",
]
