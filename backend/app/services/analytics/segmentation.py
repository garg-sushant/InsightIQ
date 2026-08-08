"""RFM scoring and K-means customer segmentation.

RFM is computed deterministically from the fact frame, then K-means clusters
customers in the standardised RFM space. Clusters are *named* by ranking their
mean RFM score, so "Champions" always means the best cluster regardless of the
arbitrary integer label scikit-learn happens to assign — without that, the
labels would shuffle between runs and the AI narrative would contradict itself.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from app.schemas.analytics import CustomerSegment, RfmSummary
from app.services.analytics.numeric import ZERO, decimal_sum, money, rate, ratio_pct

#: K-means below this many customers tells you nothing you did not already know.
MIN_CUSTOMERS_FOR_CLUSTERING = 20
#: RFM quintiles need enough customers to have five distinct buckets.
MIN_CUSTOMERS_FOR_RFM = 5

DEFAULT_CLUSTERS = 4
RANDOM_SEED = 42

#: Applied in descending order of mean RFM score.
CLUSTER_LABELS = ("Champions", "Loyal", "Promising", "At risk", "Hibernating")


def compute_rfm(frame: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Per-customer recency (days), frequency (orders) and monetary (revenue)."""
    if frame.empty:
        return pd.DataFrame(
            columns=["customer_id", "recency", "frequency", "monetary", "monetary_dec"]
        )

    reference = pd.Timestamp(as_of)
    records = []
    for customer_id, group in frame.groupby("customer_id", sort=False):
        last_order = group["order_date"].max()
        revenue = decimal_sum(group["sales"])
        records.append(
            {
                "customer_id": customer_id,
                "recency": int((reference - last_order).days),
                "frequency": int(group["order_ref"].nunique()),
                "monetary": float(revenue),
                "monetary_dec": revenue,
            }
        )
    return pd.DataFrame(records)


def score_rfm(rfm: pd.DataFrame) -> pd.DataFrame:
    """Add 1-5 R/F/M scores and their sum.

    Quintiles via ``qcut`` adapt to the tenant's own distribution rather than
    imposing absolute thresholds that would be meaningless across industries.
    ``duplicates="drop"`` handles the common case where many customers share a
    value (e.g. everyone has exactly one order).
    """
    if rfm.empty:
        return rfm

    scored = rfm.copy()
    if len(scored) < MIN_CUSTOMERS_FOR_RFM:
        scored["r_score"] = 3
        scored["f_score"] = 3
        scored["m_score"] = 3
        scored["rfm_score"] = 9
        return scored

    scored["r_score"] = _quintile(scored["recency"], reverse=True)
    scored["f_score"] = _quintile(scored["frequency"], reverse=False)
    scored["m_score"] = _quintile(scored["monetary"], reverse=False)
    scored["rfm_score"] = scored["r_score"] + scored["f_score"] + scored["m_score"]
    return scored


def _quintile(series: pd.Series, *, reverse: bool) -> pd.Series:
    """1-5 bucket. ``reverse=True`` means "lower raw value scores higher"."""
    try:
        buckets = pd.qcut(series.rank(method="first"), 5, labels=False, duplicates="drop")
    except ValueError:
        return pd.Series(3, index=series.index, dtype=int)

    buckets = pd.Series(buckets, index=series.index).fillna(0).astype(int)
    span = int(buckets.max()) or 1
    # Normalise whatever number of bins survived `duplicates="drop"` onto 1..5.
    normalised = (buckets / span * 4).round().astype(int) + 1
    return (6 - normalised) if reverse else normalised


def segment_customers(
    frame: pd.DataFrame,
    as_of: date,
    *,
    clusters: int = DEFAULT_CLUSTERS,
) -> RfmSummary:
    """Full RFM + K-means pipeline, degrading gracefully on small datasets."""
    rfm = compute_rfm(frame, as_of)
    if rfm.empty:
        return RfmSummary(
            customers_scored=0,
            clusters=0,
            segments=[],
            note="No customer activity in the selected period.",
        )

    scored = score_rfm(rfm)
    total_revenue = decimal_sum(scored["monetary_dec"])
    customer_count = len(scored)

    if customer_count < MIN_CUSTOMERS_FOR_CLUSTERING:
        # Fall back to a single descriptive group rather than inventing clusters.
        scored["cluster"] = 0
        summary = _summarise(scored, total_revenue, customer_count, label_override="All customers")
        return RfmSummary(
            customers_scored=customer_count,
            clusters=1,
            segments=summary,
            note=(
                f"{customer_count} customer(s) in range; K-means clustering needs at "
                f"least {MIN_CUSTOMERS_FOR_CLUSTERING}. Showing a single aggregate group."
            ),
        )

    features = np.column_stack(
        [
            scored["recency"].to_numpy(dtype=float),
            # Log-scale the heavy-tailed measures so a handful of whales do not
            # define every cluster boundary.
            np.log1p(scored["frequency"].to_numpy(dtype=float)),
            np.log1p(np.clip(scored["monetary"].to_numpy(dtype=float), 0, None)),
        ]
    )
    scaled = StandardScaler().fit_transform(features)

    effective_clusters = max(2, min(clusters, customer_count // 5, len(CLUSTER_LABELS)))
    model = KMeans(n_clusters=effective_clusters, random_state=RANDOM_SEED, n_init=10)
    scored["cluster"] = model.fit_predict(scaled)

    return RfmSummary(
        customers_scored=customer_count,
        clusters=effective_clusters,
        segments=_summarise(scored, total_revenue, customer_count),
        note=None,
    )


def _summarise(
    scored: pd.DataFrame,
    total_revenue: Decimal,
    customer_count: int,
    *,
    label_override: str | None = None,
) -> list[CustomerSegment]:
    groups = []
    for cluster_id, group in scored.groupby("cluster", sort=False):
        groups.append(
            {
                "cluster_id": int(cluster_id),
                "group": group,
                "mean_score": float(group["rfm_score"].mean()),
            }
        )
    # Best cluster first, so label assignment is stable across runs.
    groups.sort(key=lambda item: item["mean_score"], reverse=True)

    segments: list[CustomerSegment] = []
    for position, item in enumerate(groups):
        group: pd.DataFrame = item["group"]
        revenue = decimal_sum(group["monetary_dec"])
        label = label_override or CLUSTER_LABELS[min(position, len(CLUSTER_LABELS) - 1)]
        segments.append(
            CustomerSegment(
                cluster_id=item["cluster_id"],
                label=label,
                customer_count=len(group),
                customer_share_pct=rate(
                    ratio_pct(Decimal(len(group)), Decimal(customer_count)) or ZERO
                ),
                revenue=money(revenue),
                revenue_share_pct=rate(ratio_pct(revenue, total_revenue) or ZERO),
                avg_recency_days=round(float(group["recency"].mean()), 1),
                avg_frequency=round(float(group["frequency"].mean()), 2),
                avg_monetary=round(float(group["monetary"].mean()), 2),
                avg_rfm_score=round(item["mean_score"], 2),
            )
        )
    return segments


__all__ = [
    "CLUSTER_LABELS",
    "DEFAULT_CLUSTERS",
    "MIN_CUSTOMERS_FOR_CLUSTERING",
    "compute_rfm",
    "score_rfm",
    "segment_customers",
]
