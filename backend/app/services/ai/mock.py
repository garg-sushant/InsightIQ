"""Offline provider used whenever no AI key is configured.

This is *not* a stub that returns lorem ipsum. It composes genuine narrative
from the real figures in the payload using deterministic templates, so the
dashboard, PDF and PPTX are fully demoable before any account exists — and so
the entire test suite can exercise the AI path without a network call.

Every section it produces is explicitly labelled as generated without a live
model, and every response carries ``is_fallback=True`` so the UI can badge it.
"""

from __future__ import annotations

import time

from app.schemas.ai import AIPayload, PayloadMetric
from app.services.ai.prompts import loader
from app.services.ai.provider import AIResponse

PLACEHOLDER_NOTICE = (
    "_Generated offline by InsightIQ's built-in analyst (no AI provider configured). "
    "All figures below are the platform's own computed values; the wording is "
    "template-based rather than model-written._"
)


def _find(payload: AIPayload, key: str) -> PayloadMetric | None:
    return next((metric for metric in payload.metrics if metric.key == key), None)


def _fmt(metric: PayloadMetric | None) -> str:
    if metric is None:
        return "n/a"
    if metric.unit == "currency":
        return f"${metric.value:,.2f}"
    if metric.unit == "percent":
        return f"{metric.value:,.1f}%"
    return f"{metric.value:,.0f}"


def _movement(metric: PayloadMetric | None) -> str:
    if metric is None or metric.delta_pct is None:
        return "with no comparison period available"
    verb = "up" if metric.delta_pct > 0 else "down" if metric.delta_pct < 0 else "flat"
    if verb == "flat":
        return "essentially flat versus the comparison period"
    return f"{verb} {abs(metric.delta_pct):.1f}% versus the comparison period"


class MockProvider:
    """:class:`~app.services.ai.provider.AIProvider` implementation with no network."""

    name = "mock"
    model = "insightiq-offline-analyst"

    @property
    def is_mock(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None

    def _wrap(self, content: str, structured: dict[str, object] | None = None) -> AIResponse:
        return AIResponse(
            content=content,
            structured=structured,
            provider=self.name,
            model=self.model,
            prompt_version=loader.PROMPT_VERSION,
            is_fallback=True,
            latency_ms=int((time.perf_counter() % 1) * 10),
        )

    # -- sections -----------------------------------------------------------
    async def generate_summary(self, payload: AIPayload) -> AIResponse:
        revenue = _find(payload, "revenue")
        profit = _find(payload, "profit")
        margin = _find(payload, "margin_pct")
        orders = _find(payload, "orders")
        aov = _find(payload, "aov")
        new_customers = _find(payload, "new_customers")
        repeat_rate = _find(payload, "repeat_rate_pct")

        context = payload.context
        lines = [
            PLACEHOLDER_NOTICE,
            "",
            f"**Period {context.period_start} to {context.period_end}** "
            f"({context.period_days} days, {context.observation_count:,} order lines).",
            "",
            f"- **Revenue** reached {_fmt(revenue)}, {_movement(revenue)}.",
            f"- **Profit** was {_fmt(profit)} at a {_fmt(margin)} margin, "
            f"{_movement(profit)}.",
            f"- **{_fmt(orders)} orders** were placed at an average value of {_fmt(aov)}.",
            f"- **{_fmt(new_customers)} new customers** were acquired; the repeat-purchase "
            f"rate stands at {_fmt(repeat_rate)}.",
        ]

        if payload.segment_rollups:
            leader = max(payload.segment_rollups, key=lambda r: r.revenue_share_pct)
            lines.append(
                f"- The strongest slice is **{leader.key}** ({leader.dimension.replace('_', ' ')}), "
                f"carrying {leader.revenue_share_pct:.1f}% of revenue at a "
                f"{leader.margin_pct:.1f}% margin."
            )

        if payload.anomalies:
            worst = payload.anomalies[0]
            lines.append(
                f"- **{len(payload.anomalies)} anomalous period(s)** were detected, the most "
                f"pronounced being a {worst.direction} in {worst.metric.replace('_', ' ')} "
                f"during {worst.period}."
            )

        flagged = [risk for risk in payload.risks if risk.level not in {"ok"}]
        if flagged:
            lines.append(
                f"- **{len(flagged)} risk indicator(s)** are above threshold: "
                + ", ".join(risk.label.lower() for risk in flagged[:3])
                + "."
            )

        lines.extend(
            [
                "",
                f"Overall business health scores **{payload.health_score}/100 "
                f"(grade {payload.health_grade})**.",
            ]
        )
        return self._wrap("\n".join(lines))

    async def generate_root_cause(self, payload: AIPayload) -> AIResponse:
        movers = sorted(
            (m for m in payload.metrics if m.delta_pct is not None),
            key=lambda m: abs(m.delta_pct or 0),
            reverse=True,
        )[:3]

        causes: list[dict[str, object]] = []
        for metric in movers:
            evidence: list[str] = [
                f"{metric.label} moved {metric.delta_pct:+.1f}% "
                f"({metric.previous_value:,.2f} -> {metric.value:,.2f})."
                if metric.previous_value is not None
                else f"{metric.label} is {metric.value:,.2f}."
            ]

            declining = [
                rollup
                for rollup in payload.segment_rollups
                if rollup.revenue_delta_pct is not None and rollup.revenue_delta_pct < 0
            ]
            if declining:
                worst = min(declining, key=lambda r: r.revenue_delta_pct or 0)
                evidence.append(
                    f"{worst.key} revenue fell {abs(worst.revenue_delta_pct or 0):.1f}%, "
                    f"holding {worst.revenue_share_pct:.1f}% of the total."
                )

            for risk in payload.risks:
                if risk.level in {"elevated", "critical"}:
                    evidence.append(f"{risk.label}: {risk.description}")
                    break

            causes.append(
                {
                    "metric": metric.key,
                    "movement": (
                        f"{metric.label} moved {metric.delta_pct:+.1f}% versus the "
                        "comparison period."
                    ),
                    "hypothesis": (
                        f"The movement in {metric.label.lower()} aligns with the segment "
                        "and risk signals listed as evidence. This is a correlation drawn "
                        "from aggregate data, not a confirmed cause; validate against "
                        "operational context before acting."
                    ),
                    "supporting_evidence": evidence,
                    "confidence": "medium" if len(evidence) > 1 else "low",
                }
            )

        structured: dict[str, object] = {"root_causes": causes}
        rendered = [PLACEHOLDER_NOTICE, ""]
        if not causes:
            rendered.append(
                "No comparison period is available, so metric movements cannot be "
                "attributed. Select a date range with a preceding period to enable "
                "root-cause analysis."
            )
        for cause in causes:
            rendered.append(f"**{cause['movement']}**")
            rendered.append(str(cause["hypothesis"]))
            for item in cause["supporting_evidence"]:  # type: ignore[union-attr]
                rendered.append(f"- {item}")
            rendered.append(f"_Confidence: {cause['confidence']}._")
            rendered.append("")

        return self._wrap("\n".join(rendered).strip(), structured)

    async def generate_recommendations(self, payload: AIPayload) -> AIResponse:
        recommendations: list[dict[str, object]] = []

        by_level = {risk.key: risk for risk in payload.risks}
        playbook: list[tuple[str, str, str, str, str, str, str]] = [
            (
                "margin_erosion",
                "Rebuild margin on the weakest categories",
                "Margin is eroding across the period. Review cost-to-serve and list "
                "pricing on the lowest-margin categories before volume compounds the loss.",
                "high", "high", "medium", "margin_pct",
            ),
            (
                "loss_making_revenue",
                "Stop or reprice loss-making order lines",
                "A material share of revenue is booked at a negative margin. Identify "
                "those lines and either reprice them or withdraw them from promotion.",
                "high", "high", "low", "profit",
            ),
            (
                "discount_dependency",
                "Introduce discount approval thresholds",
                "Average discount is high enough to be structural rather than tactical. "
                "Gate discounts above the current average behind approval.",
                "high", "medium", "low", "avg_discount_pct",
            ),
            (
                "return_rate_rise",
                "Run a returns root-cause review on the worst categories",
                "The return rate is climbing. Returns destroy both revenue and margin, "
                "so isolate the driver categories and inspect product data quality.",
                "medium", "medium", "medium", "return_rate_pct",
            ),
            (
                "customer_concentration",
                "Reduce dependence on the top customer decile",
                "Revenue is concentrated in a small share of customers, so the loss of "
                "one account would be material. Fund acquisition in the mid-tier.",
                "medium", "high", "high", "revenue",
            ),
            (
                "repeat_rate_decline",
                "Launch a win-back programme for lapsing customers",
                "Repeat-purchase rate is falling, which raises acquisition cost per unit "
                "of revenue. Target the at-risk RFM segment with a retention offer.",
                "medium", "medium", "medium", "repeat_rate_pct",
            ),
            (
                "product_concentration",
                "Broaden the revenue base beyond the top ten products",
                "A narrow product base concentrates supply and demand risk. Promote "
                "adjacent sub-categories with proven margin.",
                "low", "medium", "medium", "revenue",
            ),
        ]

        severity_rank = {"critical": 0, "elevated": 1, "watch": 2, "ok": 3}
        for key, title, rationale, priority, impact, effort, watch in playbook:
            risk = by_level.get(key)
            if risk is None or risk.level == "ok":
                continue
            recommendations.append(
                {
                    "title": title,
                    "rationale": f"{rationale} Current reading: {risk.description}",
                    "priority": "high" if risk.level == "critical" else priority,
                    "impact": impact,
                    "effort": effort,
                    "owner": "Commercial leadership",
                    "metric_to_watch": watch,
                    "__rank": severity_rank.get(risk.level, 3),
                }
            )

        recommendations.sort(key=lambda item: item.pop("__rank"))  # type: ignore[arg-type]

        if not recommendations:
            recommendations.append(
                {
                    "title": "Hold course and protect the current margin structure",
                    "rationale": (
                        "No risk indicator is above threshold and business health scores "
                        f"{payload.health_score}/100. The priority is to preserve the "
                        "current pricing and mix rather than intervene."
                    ),
                    "priority": "low",
                    "impact": "medium",
                    "effort": "low",
                    "owner": "Commercial leadership",
                    "metric_to_watch": "margin_pct",
                }
            )

        structured: dict[str, object] = {"recommendations": recommendations[:6]}
        rendered = [PLACEHOLDER_NOTICE, ""]
        for position, item in enumerate(recommendations[:6], start=1):
            rendered.append(f"**{position}. {item['title']}**")
            rendered.append(str(item["rationale"]))
            rendered.append(
                f"_Priority: {item['priority']} · Impact: {item['impact']} · "
                f"Effort: {item['effort']} · Watch: {item['metric_to_watch']}_"
            )
            rendered.append("")

        return self._wrap("\n".join(rendered).strip(), structured)

    async def generate_risks(self, payload: AIPayload) -> AIResponse:
        flagged = [risk for risk in payload.risks if risk.level != "ok"]
        lines = [PLACEHOLDER_NOTICE, ""]

        if not flagged:
            lines.append(
                "All monitored risk indicators are within healthy thresholds for this "
                f"period. Business health scores {payload.health_score}/100 (grade "
                f"{payload.health_grade}). Continue monitoring margin and return rate, "
                "which are the fastest-moving indicators in this dataset."
            )
            return self._wrap("\n".join(lines))

        order = {"critical": 0, "elevated": 1, "watch": 2}
        for risk in sorted(flagged, key=lambda r: order.get(r.level, 3)):
            lines.append(
                f"- **{risk.label}** ({risk.level}) — {risk.description} "
                f"Threshold for concern is {risk.threshold:g}{'%' if risk.unit == 'percent' else ''}; "
                f"current reading is {risk.value:g}. "
                f"Monitor this indicator period-over-period; a further move in the same "
                f"direction would make it materially worse."
            )

        if payload.anomalies:
            worst = payload.anomalies[0]
            lines.append(
                f"- **Volatility** (watch) — {worst.description} Repeated deviations of "
                "this size would undermine forecast reliability."
            )

        return self._wrap("\n".join(lines))


__all__ = ["PLACEHOLDER_NOTICE", "MockProvider"]
