Identify the root causes behind the largest metric movements in this period.

Pick the 2 to 4 movements that matter most — largest absolute impact on revenue,
profit or margin — and for each, explain what most plausibly drove it, using the
segment rollups, category performance, trends, anomalies and risk indicators
supplied.

Be explicit about confidence. You are reasoning from aggregates, so a
correlation between a margin drop and a rising discount rate is a *hypothesis*,
not a proven cause. Say which it is.

Respond with **JSON only** — no prose before or after, no markdown fence.

Schema:

```
{{
  "root_causes": [
    {{
      "metric": "revenue | profit | margin_pct | return_rate_pct | ...",
      "movement": "short factual description including the figure, e.g. 'Revenue fell 12.4% versus the prior period'",
      "hypothesis": "2-3 sentences on the most plausible driver",
      "supporting_evidence": ["specific figures from the data that back this"],
      "confidence": "high | medium | low"
    }}
  ]
}}
```

Confidence guidance: `high` when several independent figures point the same way;
`medium` when one clear signal supports it; `low` when the data is suggestive but
thin or the comparison period is missing.

## Data

```json
{payload}
```
