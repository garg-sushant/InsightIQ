Produce prioritised strategic recommendations based on this period's results.

Give 3 to 6 recommendations. Each must be an action someone could actually start
this quarter — not a restatement of the problem. Tie each one to the specific
figure that motivates it.

Order them by expected impact, highest first.

Respond with **JSON only** — no prose before or after, no markdown fence.

Schema:

```
{{
  "recommendations": [
    {{
      "title": "imperative, under 90 characters, e.g. 'Cap discounting on Furniture below 20%'",
      "rationale": "2-3 sentences citing the figures that motivate this",
      "priority": "high | medium | low",
      "impact": "high | medium | low",
      "effort": "high | medium | low",
      "owner": "the function that should own it, e.g. 'Pricing', 'Category management', 'Customer success'",
      "metric_to_watch": "the metric key that should move if this works, e.g. 'margin_pct'"
    }}
  ]
}}
```

`metric_to_watch` must be one of the metric keys present in the supplied data.

## Data

```json
{payload}
```
