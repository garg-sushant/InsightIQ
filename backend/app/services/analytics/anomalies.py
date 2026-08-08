"""Anomaly detection over the revenue and margin series.

Two detectors run together, deliberately:

* **Isolation Forest** (scikit-learn) over the joint feature space of level,
  margin and period-over-period change. It finds unusual *combinations* — a
  normal revenue period with a collapsed margin, say — that no single-metric
  rule would catch.
* **Modified z-score** (median/MAD, Iglewicz-Hoaglin) per metric. Robust to the
  very outliers it is looking for, unlike a mean/σ z-score which an extreme
  point inflates until it hides itself.

Both are seeded and deterministic: the same data always yields the same
anomalies, which matters because an AI narrative is written on top of them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.schemas.analytics import (
    AnomalyPoint,
    AnomalyReport,
    AnomalySeverity,
    Granularity,
)
from app.services.analytics.numeric import ZERO, ratio_pct
from app.services.analytics.timeseries import aggregate_periods, fill_missing_periods

#: Isolation Forest needs a reasonable sample before its scores mean anything.
MIN_POINTS_FOR_FOREST = 20
#: The rule-based detector needs enough points for a stable median/MAD.
MIN_POINTS_FOR_ZSCORE = 8

DEFAULT_CONTAMINATION = 0.05
#: Iglewicz-Hoaglin recommend 3.5 for the modified z-score.
ZSCORE_THRESHOLD = 3.5
#: Below this, a "deviation" is noise not news.
MIN_DEVIATION_PCT = 10.0

RANDOM_SEED = 42
_MAD_SCALE = 0.6745


def _severity(deviation_pct: float) -> AnomalySeverity:
    magnitude = abs(deviation_pct)
    if magnitude >= 50:
        return AnomalySeverity.HIGH
    if magnitude >= 25:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.LOW


def _modified_zscores(values: np.ndarray) -> np.ndarray:
    """Median/MAD z-scores, falling back to std when MAD is zero."""
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad > 0:
        return _MAD_SCALE * (values - median) / mad
    std = float(np.std(values))
    if std > 0:
        return (values - median) / std
    return np.zeros_like(values)


def _series_frame(frame: pd.DataFrame, granularity: Granularity) -> pd.DataFrame:
    aggregated = fill_missing_periods(aggregate_periods(frame, granularity), granularity)
    if aggregated.empty:
        return aggregated

    aggregated = aggregated.copy()
    aggregated["revenue_f"] = aggregated["revenue"].astype(float)
    aggregated["profit_f"] = aggregated["profit"].astype(float)
    aggregated["margin_pct"] = [
        float(ratio_pct(profit, revenue) or ZERO)
        for profit, revenue in zip(aggregated["profit"], aggregated["revenue"], strict=True)
    ]
    aggregated["revenue_change"] = aggregated["revenue_f"].pct_change().fillna(0.0) * 100
    return aggregated


def detect_anomalies(
    frame: pd.DataFrame,
    granularity: Granularity,
    *,
    contamination: float = DEFAULT_CONTAMINATION,
) -> AnomalyReport:
    """Run both detectors and merge their findings."""
    series = _series_frame(frame, granularity)
    point_count = len(series)

    if point_count < MIN_POINTS_FOR_ZSCORE:
        return AnomalyReport(
            granularity=granularity,
            points_analysed=point_count,
            contamination=contamination,
            anomalies=[],
            note=(
                f"Only {point_count} {granularity.value} period(s) in range; "
                f"anomaly detection needs at least {MIN_POINTS_FOR_ZSCORE}."
            ),
        )

    anomalies: list[AnomalyPoint] = []
    anomalies.extend(_rule_based(series))

    note: str | None = None
    if point_count >= MIN_POINTS_FOR_FOREST:
        anomalies.extend(_isolation_forest(series, contamination))
    else:
        note = (
            f"Isolation Forest skipped: {point_count} periods available, "
            f"{MIN_POINTS_FOR_FOREST} required. Rule-based detection still ran."
        )

    # One period+metric can be flagged by both detectors; keep the stronger one.
    deduped: dict[tuple[str, str], AnomalyPoint] = {}
    for anomaly in anomalies:
        key = (anomaly.period, anomaly.metric)
        existing = deduped.get(key)
        if existing is None or abs(anomaly.deviation_pct) > abs(existing.deviation_pct):
            deduped[key] = anomaly

    ordered = sorted(
        deduped.values(), key=lambda a: abs(a.deviation_pct), reverse=True
    )
    return AnomalyReport(
        granularity=granularity,
        points_analysed=point_count,
        contamination=contamination,
        anomalies=ordered,
        note=note,
    )


def _rule_based(series: pd.DataFrame) -> list[AnomalyPoint]:
    findings: list[AnomalyPoint] = []
    for metric, column in (("revenue", "revenue_f"), ("margin_pct", "margin_pct")):
        values = series[column].to_numpy(dtype=float)
        if not np.isfinite(values).all() or len(values) < MIN_POINTS_FOR_ZSCORE:
            continue

        scores = _modified_zscores(values)
        baseline = float(np.median(values))

        for position, score in enumerate(scores):
            if abs(score) < ZSCORE_THRESHOLD:
                continue
            value = float(values[position])
            deviation = _deviation_pct(value, baseline, metric)
            if abs(deviation) < MIN_DEVIATION_PCT:
                continue
            direction = "spike" if value > baseline else "drop"
            period = pd.Timestamp(series["period"].iloc[position]).date().isoformat()
            findings.append(
                AnomalyPoint(
                    period=period,
                    metric=metric,  # type: ignore[arg-type]
                    value=round(value, 2),
                    expected=round(baseline, 2),
                    deviation_pct=round(deviation, 2),
                    z_score=round(float(score), 2),
                    severity=_severity(deviation),
                    direction=direction,  # type: ignore[arg-type]
                    method="zscore_rule",
                    description=(
                        f"{metric.replace('_', ' ').title()} of "
                        f"{value:,.2f} is a {abs(deviation):.0f}% {direction} versus the "
                        f"typical {baseline:,.2f} for this range "
                        f"(modified z-score {score:.1f})."
                    ),
                )
            )
    return findings


def _isolation_forest(series: pd.DataFrame, contamination: float) -> list[AnomalyPoint]:
    features = series[["revenue_f", "margin_pct", "revenue_change"]].to_numpy(dtype=float)
    if not np.isfinite(features).all():
        return []

    # Standardise so revenue (thousands) does not swamp margin (tens).
    means = features.mean(axis=0)
    stds = features.std(axis=0)
    stds[stds == 0] = 1.0
    scaled = (features - means) / stds

    model = IsolationForest(
        contamination=contamination,
        random_state=RANDOM_SEED,
        n_estimators=200,
        bootstrap=False,
    )
    labels = model.fit_predict(scaled)

    revenue_values = series["revenue_f"].to_numpy(dtype=float)
    baseline = float(np.median(revenue_values))

    findings: list[AnomalyPoint] = []
    for position in np.flatnonzero(labels == -1):
        value = float(revenue_values[position])
        deviation = _deviation_pct(value, baseline, "revenue")
        if abs(deviation) < MIN_DEVIATION_PCT:
            continue
        direction = "spike" if value > baseline else "drop"
        margin_value = float(series["margin_pct"].iloc[position])
        period = pd.Timestamp(series["period"].iloc[position]).date().isoformat()
        findings.append(
            AnomalyPoint(
                period=period,
                metric="revenue",
                value=round(value, 2),
                expected=round(baseline, 2),
                deviation_pct=round(deviation, 2),
                z_score=None,
                severity=_severity(deviation),
                direction=direction,  # type: ignore[arg-type]
                method="isolation_forest",
                description=(
                    f"Isolation Forest flagged this period as an outlier: revenue "
                    f"{value:,.2f} ({abs(deviation):.0f}% {direction} vs typical) "
                    f"with a {margin_value:.1f}% margin."
                ),
            )
        )
    return findings


def _deviation_pct(value: float, baseline: float, metric: str) -> float:
    """Percentage deviation, or percentage-*point* deviation for rate metrics."""
    if metric == "margin_pct":
        return value - baseline
    if baseline == 0:
        return 0.0
    return (value - baseline) / abs(baseline) * 100


def anomaly_summary(report: AnomalyReport) -> str:
    """One-line human summary, reused by the AI payload and the PDF."""
    if not report.anomalies:
        return "No statistically significant anomalies detected in the selected period."
    high = sum(1 for a in report.anomalies if a.severity is AnomalySeverity.HIGH)
    return (
        f"{len(report.anomalies)} anomalous period(s) detected"
        + (f", {high} of high severity" if high else "")
        + "."
    )


__all__ = [
    "DEFAULT_CONTAMINATION",
    "MIN_POINTS_FOR_FOREST",
    "MIN_POINTS_FOR_ZSCORE",
    "ZSCORE_THRESHOLD",
    "anomaly_summary",
    "detect_anomalies",
]
