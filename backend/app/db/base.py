"""Single import target that guarantees every model is registered on the metadata.

Alembic's ``env.py`` imports this rather than reaching into ``app.models``
piecemeal, so a newly added model can never be silently missing from a
migration autogenerate run.
"""

from app.models import (  # noqa: F401  (imported for metadata registration)
    AIInsight,
    AnalysisRun,
    AuditLog,
    Base,
    Customer,
    Dataset,
    Order,
    Organization,
    Product,
    Return,
    User,
)

target_metadata = Base.metadata

__all__ = ["Base", "target_metadata"]
