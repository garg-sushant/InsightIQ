"""Server-side chart rendering with Matplotlib's Agg backend.

Charts are drawn from the persisted :class:`AnalyticsResult`, never captured
from the frontend — the exports must work headlessly on the API host with no
browser involved.
"""

from __future__ import annotations

import io

import matplotlib

# Must be selected before pyplot is imported; the API host has no display.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from app.schemas.analytics import AnalyticsResult  # noqa: E402

DPI = 150

# Muted, print-safe palette. Deliberately not the frontend's dark theme —
# reports are read on paper and in slide decks.
INK = "#1f2933"
MUTED = "#7b8794"
GRID = "#e4e7eb"
ACCENT = "#2563eb"
ACCENT_SOFT = "#93c5fd"
POSITIVE = "#059669"
NEGATIVE = "#dc2626"
CATEGORICAL = ("#2563eb", "#0891b2", "#7c3aed", "#db2777", "#ea580c", "#65a30d")


def _currency(value: float, _position: int = 0) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if absolute >= 1_000:
        return f"${value / 1_000:,.0f}K"
    return f"${value:,.0f}"


def _style(axes: plt.Axes, *, title: str, ylabel: str | None = None) -> None:
    axes.set_title(title, fontsize=11, color=INK, pad=10, loc="left", fontweight="bold")
    if ylabel:
        axes.set_ylabel(ylabel, fontsize=8, color=MUTED)
    axes.tick_params(colors=MUTED, labelsize=8)
    axes.grid(axis="y", color=GRID, linewidth=0.8)
    axes.set_axisbelow(True)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(GRID)


def _render(figure: Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=DPI, bbox_inches="tight",
                   facecolor="white", edgecolor="none")
    plt.close(figure)
    buffer.seek(0)
    return buffer.read()


def _placeholder(title: str, message: str) -> bytes:
    figure, axes = plt.subplots(figsize=(7.2, 3.2))
    axes.text(0.5, 0.5, message, ha="center", va="center", fontsize=10, color=MUTED,
              wrap=True)
    axes.set_title(title, fontsize=11, color=INK, loc="left", fontweight="bold")
    axes.axis("off")
    return _render(figure)


def revenue_trend_chart(result: AnalyticsResult) -> bytes:
    """Revenue and profit over time, with the revenue moving average."""
    points = result.timeseries.points
    if len(points) < 2:
        return _placeholder(
            "Revenue and profit trend",
            "Not enough periods in the selected range to draw a trend.",
        )

    labels = [point.period for point in points]
    revenue = [point.revenue for point in points]
    profit = [point.profit for point in points]
    moving = [point.revenue_ma or 0.0 for point in points]

    figure, axes = plt.subplots(figsize=(9.0, 3.6))
    axes.fill_between(labels, revenue, color=ACCENT_SOFT, alpha=0.35)
    axes.plot(labels, revenue, color=ACCENT, linewidth=2.0, label="Revenue")
    axes.plot(labels, moving, color=INK, linewidth=1.2, linestyle="--",
              label=f"{result.timeseries.moving_average_window}-period average")
    axes.plot(labels, profit, color=POSITIVE, linewidth=1.6, label="Profit")

    _style(axes, title="Revenue and profit trend")
    axes.yaxis.set_major_formatter(FuncFormatter(_currency))
    _thin_xticks(axes, len(labels))
    axes.legend(frameon=False, fontsize=8, labelcolor=MUTED, ncol=3, loc="upper left")
    return _render(figure)


def _thin_xticks(axes: plt.Axes, count: int, target: int = 12) -> None:
    """Keep the x-axis readable regardless of how many periods there are."""
    if count <= target:
        plt.setp(axes.get_xticklabels(), rotation=45, ha="right")
        return
    step = max(1, count // target)
    for position, label in enumerate(axes.get_xticklabels()):
        label.set_visible(position % step == 0)
    plt.setp(axes.get_xticklabels(), rotation=45, ha="right")


def breakdown_chart(result: AnalyticsResult, dimension: str, title: str) -> bytes:
    """Horizontal revenue bars for one dimension."""
    breakdown = result.breakdowns.get(dimension)
    if breakdown is None or not breakdown.items:
        return _placeholder(title, "No data for this dimension in the selected range.")

    items = breakdown.items[:8][::-1]
    labels = [item.label for item in items]
    values = [item.revenue for item in items]

    figure, axes = plt.subplots(figsize=(4.4, max(2.4, 0.42 * len(items) + 1.0)))
    bars = axes.barh(labels, values, color=ACCENT, height=0.62)
    axes.bar_label(bars, labels=[_currency(v) for v in values], padding=4,
                   fontsize=7.5, color=MUTED)

    _style(axes, title=title)
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=GRID, linewidth=0.8)
    axes.xaxis.set_major_formatter(FuncFormatter(_currency))
    axes.margins(x=0.18)
    return _render(figure)


def margin_by_category_chart(result: AnalyticsResult) -> bytes:
    """Margin percentage by category, coloured by sign."""
    breakdown = result.breakdowns.get("category")
    if breakdown is None or not breakdown.items:
        return _placeholder("Margin by category", "No category data in the selected range.")

    items = breakdown.items[:8]
    labels = [item.label for item in items]
    values = [item.margin_pct for item in items]
    colors = [POSITIVE if value >= 0 else NEGATIVE for value in values]

    figure, axes = plt.subplots(figsize=(4.4, 3.0))
    bars = axes.bar(labels, values, color=colors, width=0.6)
    axes.bar_label(bars, labels=[f"{v:.1f}%" for v in values], padding=3,
                   fontsize=7.5, color=MUTED)
    axes.axhline(0, color=MUTED, linewidth=0.8)

    _style(axes, title="Margin by category", ylabel="Margin %")
    plt.setp(axes.get_xticklabels(), rotation=30, ha="right")
    return _render(figure)


def segment_chart(result: AnalyticsResult) -> bytes:
    """Revenue share by customer segment (RFM clusters)."""
    segments = result.rfm.segments
    if not segments:
        return _placeholder(
            "Customer segments", "Not enough customers in range to build segments."
        )

    labels = [segment.label for segment in segments]
    values = [segment.revenue_share_pct for segment in segments]

    figure, axes = plt.subplots(figsize=(4.4, 3.2))
    wedges, _, autotexts = axes.pie(
        values,
        labels=labels,
        autopct="%1.0f%%",
        colors=CATEGORICAL[: len(values)],
        startangle=90,
        wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 1.5},
        textprops={"fontsize": 8, "color": INK},
    )
    for text in autotexts:
        text.set_color("white")
        text.set_fontsize(7.5)
    axes.set_title("Revenue share by customer segment", fontsize=11, color=INK,
                   loc="left", fontweight="bold")
    del wedges
    return _render(figure)


def top_products_chart(result: AnalyticsResult) -> bytes:
    """Most profitable products."""
    products = result.top_products[:8]
    if not products:
        return _placeholder("Top products by profit", "No product data in the selected range.")

    items = products[::-1]
    labels = [
        (product.name[:34] + "…") if len(product.name) > 35 else product.name
        for product in items
    ]
    values = [product.profit for product in items]

    figure, axes = plt.subplots(figsize=(9.0, max(2.6, 0.42 * len(items) + 1.0)))
    bars = axes.barh(labels, values, color=POSITIVE, height=0.62)
    axes.bar_label(bars, labels=[_currency(v) for v in values], padding=4,
                   fontsize=7.5, color=MUTED)

    _style(axes, title="Most profitable products")
    axes.grid(axis="y", visible=False)
    axes.grid(axis="x", color=GRID, linewidth=0.8)
    axes.xaxis.set_major_formatter(FuncFormatter(_currency))
    axes.margins(x=0.15)
    return _render(figure)


def build_chart_set(result: AnalyticsResult) -> dict[str, bytes]:
    """Every chart embedded in the PDF and PPTX, rendered once and shared."""
    return {
        "revenue_trend": revenue_trend_chart(result),
        "region": breakdown_chart(result, "region", "Revenue by region"),
        "category": breakdown_chart(result, "category", "Revenue by category"),
        "margin_category": margin_by_category_chart(result),
        "segments": segment_chart(result),
        "top_products": top_products_chart(result),
    }


__all__ = [
    "breakdown_chart",
    "build_chart_set",
    "margin_by_category_chart",
    "revenue_trend_chart",
    "segment_chart",
    "top_products_chart",
]
