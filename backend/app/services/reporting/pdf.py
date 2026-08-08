"""Executive PDF export (ReportLab)."""

from __future__ import annotations

import io
from datetime import UTC, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas.ai import InsightBundle
from app.schemas.analytics import AnalyticsResult, KpiSet, RiskLevel
from app.services.reporting.markdown import to_blocks, to_reportlab

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#616e7c")
ACCENT = colors.HexColor("#2563eb")
LIGHT = colors.HexColor("#f5f7fa")
BORDER = colors.HexColor("#e4e7eb")
POSITIVE = colors.HexColor("#059669")
NEGATIVE = colors.HexColor("#dc2626")

_LEVEL_COLORS = {
    RiskLevel.OK: colors.HexColor("#059669"),
    RiskLevel.WATCH: colors.HexColor("#d97706"),
    RiskLevel.ELEVATED: colors.HexColor("#ea580c"),
    RiskLevel.CRITICAL: colors.HexColor("#dc2626"),
}

PAGE_WIDTH = A4[0]
MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "IIQTitle", parent=base["Title"], fontSize=22, leading=26,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "IIQSubtitle", parent=base["Normal"], fontSize=10, leading=14,
            textColor=MUTED, spaceAfter=14,
        ),
        "h2": ParagraphStyle(
            "IIQH2", parent=base["Heading2"], fontSize=13, leading=17,
            textColor=INK, spaceBefore=14, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "IIQH3", parent=base["Heading3"], fontSize=10.5, leading=14,
            textColor=INK, spaceBefore=8, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "IIQBody", parent=base["Normal"], fontSize=9.5, leading=14,
            textColor=INK, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "IIQBullet", parent=base["Normal"], fontSize=9.5, leading=14,
            textColor=INK, leftIndent=10, bulletIndent=2, spaceAfter=3,
        ),
        "note": ParagraphStyle(
            "IIQNote", parent=base["Normal"], fontSize=8, leading=11,
            textColor=MUTED, spaceAfter=8,
        ),
        "cell": ParagraphStyle(
            "IIQCell", parent=base["Normal"], fontSize=8, leading=11, textColor=INK,
        ),
    }


def _fmt_currency(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_delta(delta_pct: float | None, *, points: bool = False) -> str:
    if delta_pct is None:
        return "—"
    suffix = " pp" if points else "%"
    return f"{delta_pct:+.1f}{suffix}"


def _kpi_table(kpis: KpiSet, styles: dict[str, ParagraphStyle]) -> Table:
    rows: list[tuple[str, str, str, bool]] = [
        ("Revenue", _fmt_currency(kpis.revenue.current), _fmt_delta(kpis.revenue.delta_pct), True),
        ("Profit", _fmt_currency(kpis.profit.current), _fmt_delta(kpis.profit.delta_pct), True),
        ("Margin", f"{kpis.margin_pct.current:,.1f}%",
         _fmt_delta(kpis.margin_pct.delta_abs, points=True), True),
        ("Orders", f"{kpis.orders.current:,.0f}", _fmt_delta(kpis.orders.delta_pct), True),
        ("Avg order value", _fmt_currency(kpis.aov.current), _fmt_delta(kpis.aov.delta_pct), True),
        ("Units sold", f"{kpis.units.current:,.0f}", _fmt_delta(kpis.units.delta_pct), True),
        ("Return rate", f"{kpis.return_rate_pct.current:,.1f}%",
         _fmt_delta(kpis.return_rate_pct.delta_abs, points=True), False),
        ("Active customers", f"{kpis.customers.current:,.0f}",
         _fmt_delta(kpis.customers.delta_pct), True),
        ("New customers", f"{kpis.new_customers.current:,.0f}",
         _fmt_delta(kpis.new_customers.delta_pct), True),
        ("Repeat rate", f"{kpis.repeat_rate_pct.current:,.1f}%",
         _fmt_delta(kpis.repeat_rate_pct.delta_abs, points=True), True),
        ("Avg discount", f"{kpis.avg_discount_pct.current:,.1f}%",
         _fmt_delta(kpis.avg_discount_pct.delta_abs, points=True), False),
    ]

    data = [["Metric", "Value", "vs comparison"]]
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]

    for index, (label, value, delta, higher_is_better) in enumerate(rows, start=1):
        data.append([label, value, delta])
        if delta != "—":
            improving = delta.startswith("+") is higher_is_better
            style_commands.append(
                ("TEXTCOLOR", (2, index), (2, index), POSITIVE if improving else NEGATIVE)
            )

    table = Table(data, colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.25,
                                   CONTENT_WIDTH * 0.25])
    table.setStyle(TableStyle(style_commands))
    del styles
    return table


def _health_block(result: AnalyticsResult, styles: dict[str, ParagraphStyle]) -> list[object]:
    health = result.health
    flow: list[object] = [
        Paragraph("Business health", styles["h2"]),
        Paragraph(
            f"<b>{health.score}/100 — grade {health.grade}.</b> {health.headline}",
            styles["body"],
        ),
    ]

    data = [["Indicator", "Level", "Reading", "Detail"]]
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for index, indicator in enumerate(health.indicators, start=1):
        data.append(
            [
                Paragraph(indicator.label, styles["cell"]),
                indicator.level.value.title(),
                f"{indicator.value:g}{'%' if indicator.unit == 'percent' else ''}",
                Paragraph(indicator.description, styles["cell"]),
            ]
        )
        style_commands.append(
            ("TEXTCOLOR", (1, index), (1, index), _LEVEL_COLORS[indicator.level])
        )

    table = Table(
        data,
        colWidths=[CONTENT_WIDTH * 0.24, CONTENT_WIDTH * 0.12,
                   CONTENT_WIDTH * 0.12, CONTENT_WIDTH * 0.52],
    )
    table.setStyle(TableStyle(style_commands))
    flow.append(table)
    return flow


def _narrative(
    title: str, markdown: str, styles: dict[str, ParagraphStyle]
) -> list[object]:
    flow: list[object] = [Paragraph(title, styles["h2"])]
    for block in to_blocks(markdown):
        rendered = to_reportlab(block.text)
        if block.kind == "bullet":
            flow.append(Paragraph(rendered, styles["bullet"], bulletText="•"))
        elif block.kind == "heading":
            flow.append(Paragraph(rendered, styles["h3"]))
        else:
            flow.append(Paragraph(rendered, styles["body"]))
    return flow


def _image(png: bytes, width: float) -> Image:
    """Scale a rendered chart to the target width, preserving aspect ratio."""
    reader = io.BytesIO(png)
    image = Image(reader)
    ratio = image.imageHeight / image.imageWidth
    image.drawWidth = width
    image.drawHeight = width * ratio
    return image


def _product_table(
    result: AnalyticsResult, styles: dict[str, ParagraphStyle]
) -> list[object]:
    if not result.top_products and not result.bottom_products:
        return []

    flow: list[object] = [Paragraph("Product performance", styles["h2"])]
    for heading, products in (
        ("Most profitable", result.top_products[:5]),
        ("Least profitable", result.bottom_products[:5]),
    ):
        if not products:
            continue
        data = [[heading, "Revenue", "Profit", "Margin", "Units"]]
        for product in products:
            data.append(
                [
                    Paragraph(product.name, styles["cell"]),
                    _fmt_currency(product.revenue),
                    _fmt_currency(product.profit),
                    f"{product.margin_pct:,.1f}%",
                    f"{product.units:,}",
                ]
            )
        table = Table(
            data,
            colWidths=[CONTENT_WIDTH * 0.40, CONTENT_WIDTH * 0.16,
                       CONTENT_WIDTH * 0.16, CONTENT_WIDTH * 0.14, CONTENT_WIDTH * 0.14],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
                    ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        flow.extend([Spacer(1, 6), table])
    return flow


def _footer(canvas: object, document: object) -> None:
    canvas.saveState()  # type: ignore[attr-defined]
    canvas.setFont("Helvetica", 7)  # type: ignore[attr-defined]
    canvas.setFillColor(MUTED)  # type: ignore[attr-defined]
    canvas.drawString(  # type: ignore[attr-defined]
        MARGIN, 10 * mm,
        "Generated by InsightIQ · Figures computed deterministically from source data",
    )
    canvas.drawRightString(  # type: ignore[attr-defined]
        PAGE_WIDTH - MARGIN, 10 * mm, f"Page {document.page}"  # type: ignore[attr-defined]
    )
    canvas.restoreState()  # type: ignore[attr-defined]


def build_pdf(
    *,
    result: AnalyticsResult,
    charts: dict[str, bytes],
    insights: InsightBundle | None,
    organization_name: str,
    title: str | None = None,
    include_charts: bool = True,
) -> bytes:
    """Render the executive PDF."""
    styles = _styles()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=20 * mm,
        title=title or "InsightIQ Executive Report",
        author="InsightIQ",
    )

    period = result.period
    flow: list[object] = [
        Paragraph(title or "Executive Business Review", styles["title"]),
        Paragraph(
            f"{organization_name} · {period.start:%d %b %Y} – {period.end:%d %b %Y} "
            f"({period.days} days) · {result.row_count:,} order lines analysed",
            styles["subtitle"],
        ),
        _kpi_table(result.kpis, styles),
        Spacer(1, 4),
        Paragraph(
            "Percentage metrics show percentage-point movement; currency and count "
            "metrics show relative change against the comparison period "
            f"({period.comparison_mode.value.replace('_', ' ')}).",
            styles["note"],
        ),
    ]

    if include_charts:
        flow.extend(
            [
                Spacer(1, 6),
                _image(charts["revenue_trend"], CONTENT_WIDTH),
                Spacer(1, 8),
                Table(
                    [[_image(charts["region"], CONTENT_WIDTH * 0.48),
                      _image(charts["category"], CONTENT_WIDTH * 0.48)]],
                    colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5],
                    style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
                ),
                PageBreak(),
                Table(
                    [[_image(charts["margin_category"], CONTENT_WIDTH * 0.48),
                      _image(charts["segments"], CONTENT_WIDTH * 0.48)]],
                    colWidths=[CONTENT_WIDTH * 0.5, CONTENT_WIDTH * 0.5],
                    style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]),
                ),
                Spacer(1, 8),
                _image(charts["top_products"], CONTENT_WIDTH),
            ]
        )

    flow.append(PageBreak())
    flow.extend(_health_block(result, styles))
    flow.extend(_product_table(result, styles))

    if result.anomalies.anomalies:
        flow.append(Paragraph("Detected anomalies", styles["h2"]))
        for anomaly in result.anomalies.anomalies[:8]:
            flow.append(
                Paragraph(
                    f"<b>{anomaly.period}</b> — {to_reportlab(anomaly.description)} "
                    f"({anomaly.severity.value} severity, {anomaly.method.replace('_', ' ')})",
                    styles["bullet"],
                    bulletText="•",
                )
            )

    if insights is not None:
        flow.append(PageBreak())
        flow.append(Paragraph("AI-generated narrative", styles["h2"]))
        flow.append(
            Paragraph(
                "The following sections are written by a language model reading only "
                "the aggregated metrics above. No raw records were shared. All figures "
                "originate from InsightIQ's deterministic analytics engine."
                + (
                    " <b>This report was produced without a live AI provider; narrative "
                    "is template-generated placeholder text.</b>"
                    if insights.degraded
                    else ""
                ),
                styles["note"],
            )
        )
        for heading, insight in (
            ("Executive summary", insights.executive_summary),
            ("Root-cause analysis", insights.root_cause),
            ("Strategic recommendations", insights.recommendations),
            ("Risks to watch", insights.risks),
        ):
            if insight is None:
                continue
            blocks = _narrative(heading, insight.content, styles)
            # Keep the heading with its first paragraph so a section never
            # starts orphaned at the bottom of a page.
            flow.append(KeepTogether(blocks[:2]))
            flow.extend(blocks[2:])

    flow.append(Spacer(1, 10))
    flow.append(
        Paragraph(
            f"Report generated {datetime.now(UTC):%d %b %Y %H:%M UTC} · "
            f"Analysis computed {result.computed_at:%d %b %Y %H:%M UTC}",
            styles["note"],
        )
    )

    document.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    return buffer.read()


__all__ = ["build_pdf"]
