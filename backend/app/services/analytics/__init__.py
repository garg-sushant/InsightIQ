"""Deterministic analytics engine.

Every number that reaches the dashboard, a report or the AI layer originates
here, computed from SQL projections with Pandas/NumPy/scikit-learn. The AI
layer is a consumer of this module's output and never a producer of it.
"""

from app.services.analytics.anomalies import detect_anomalies
from app.services.analytics.breakdowns import build_all_breakdowns, build_product_performance
from app.services.analytics.frame import build_frame, slice_period
from app.services.analytics.kpis import CoreMetrics, build_kpi_set, compute_core_metrics
from app.services.analytics.risk import build_business_health, build_risk_indicators
from app.services.analytics.segmentation import segment_customers
from app.services.analytics.service import AnalyticsService
from app.services.analytics.timeseries import build_timeseries

__all__ = [
    "AnalyticsService",
    "CoreMetrics",
    "build_all_breakdowns",
    "build_business_health",
    "build_frame",
    "build_kpi_set",
    "build_product_performance",
    "build_risk_indicators",
    "build_timeseries",
    "compute_core_metrics",
    "detect_anomalies",
    "segment_customers",
    "slice_period",
]
