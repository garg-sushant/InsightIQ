"""PDF and PowerPoint export.

Charts are rendered server-side with Matplotlib (Agg) and embedded directly —
the frontend is never screenshotted, so exports work headlessly.
"""

from app.services.reporting.charts import build_chart_set
from app.services.reporting.pdf import build_pdf
from app.services.reporting.pptx import build_pptx
from app.services.reporting.service import GeneratedReport, ReportService

__all__ = [
    "GeneratedReport",
    "ReportService",
    "build_chart_set",
    "build_pdf",
    "build_pptx",
]
