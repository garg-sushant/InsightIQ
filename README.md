# InsightIQ

AI Business Analytics & Decision Support Platform for retail sales data.
Upload Orders, Customers, Products and Returns; get deterministic KPIs,
anomaly detection, customer segmentation and risk scoring computed by
SQL/Pandas/scikit-learn — then an AI layer writes an executive summary,
root-cause analysis and prioritized recommendations *over those exact
numbers*. Export to PDF or PowerPoint at any time.

**The core guarantee:** the AI never calculates anything and never sees raw
data. See [Architecture → the AI boundary](#the-ai-boundary) below.

## Quick start

```bash
git clone <this-repo-url-once-you-have-one>
cd insightiq
cp .env.example .env
docker compose up --build
```

Then seed realistic ~2-year demo data:

```bash
docker compose exec backend python -m app.db.seed
```

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs
- Demo login: `demo@insightiq.io` / `DemoPass123!`

No external accounts are required. AI narrative runs on a built-in offline
analyst (`MockProvider`) until you optionally add a Grok API key — see
[SETUP_REQUIRED.md](./SETUP_REQUIRED.md).

## Stack

Next.js 15 (App Router) · React 19 · TypeScript strict · Tailwind CSS ·
shadcn/ui-style components · TanStack Query · React Hook Form · Zod · Recharts
· FastAPI · SQLAlchemy 2.x async · Pydantic v2 · PostgreSQL · Pandas/NumPy/
scikit-learn · ReportLab · python-pptx · Grok API (xAI) behind a provider
abstraction · Docker Compose.

## Repository layout

```
insightiq/
  backend/app/
    api/v1/              # routes — binding + shaping only, no business logic
    core/                 # config, security, deps, exceptions, logging
    models/ schemas/ repositories/
    services/
      ingestion/          # parse -> validate -> persist
      analytics/          # deterministic KPIs, trends, anomalies, RFM, risk
      ai/                 # payload boundary, provider abstraction, prompts
      reporting/           # server-side charts, PDF, PPTX
    db/                    # session, base, alembic migrations, seed.py
  backend/tests/           # 28 tests: correctness, isolation, AI boundary, RBAC
  frontend/src/
    app/                    # pages (auth, dashboard, datasets, reports, settings)
    components/{ui,charts,dashboard,forms}/
    lib/ types/
  docker-compose.yml
```

Layering is enforced: `routes → services → repositories → models`. No DB
sessions in routes, no business logic in routes, no HTTP concerns in services.

## The AI boundary

`app/services/ai/payload.py::build_ai_payload` is the **only** function
allowed to turn analytics output into something an AI provider sees. Its
output type, `AIPayload`, is a Pydantic model with `extra="forbid"` composed
exclusively of aggregates: KPIs with deltas, dimension rollups (region,
category, segment), trend descriptions, anomaly flags, risk indicators and
customer-segment profiles. It structurally excludes row-level records, names,
emails, addresses and database identifiers — there is no field on the model
that could carry them.

`tests/test_ai_payload_boundary.py` plants realistic PII/row-level leaks in a
fixture analytics result (an email in a top-product name, a raw UUID, a
customer-identifying ref) and asserts none of it survives into the payload,
plus a structural regex sweep for anything email- or UUID-shaped anywhere in
the serialized output.

The AI layer is a **provider abstraction** (`app/services/ai/provider.py`):
`GrokProvider` and `MockProvider` both implement `generate_summary`,
`generate_root_cause`, `generate_recommendations`, `generate_risks` against
the same `AIPayload` input. Swapping in OpenAI, Gemini or a local model means
writing one new class and setting `AI_PROVIDER` — zero changes to routes,
services, or the payload boundary. Prompts live in versioned files under
`app/services/ai/prompts/*.v1.md`, never as inline strings.

**Graceful degradation:** if the configured provider is unreachable, times
out, or returns malformed output, `AIService` falls back to `MockProvider`
mid-request, tags the result `is_fallback=True`, and the dashboard/PDF/PPTX
show a clearly labelled "offline analyst" badge. The dashboard, analytics
engine, ingestion, and both export formats work fully with zero AI provider
configured — this is exercised by every test, since the whole suite runs
`AI_PROVIDER=mock` and makes no network calls.

## Multi-tenancy

Every business table carries `organization_id`. All reads and writes to
tenant-owned tables go through `OrgScopedRepository` (`app/repositories/base.py`),
which filters every `SELECT` by the caller's organization and stamps
`organization_id` on every `INSERT` — a service cannot construct a query that
skips tenant scoping, because it never gets to write raw `select()` calls
against tenant models. `tests/test_tenant_isolation.py` proves this at both
the repository layer and end-to-end over HTTP (two signed-up organizations;
org B gets 404s and zero-count listings against org A's data through every
relevant endpoint).

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

28 tests, all offline (SQLite in-memory, `AI_PROVIDER=mock`, no network
calls): hand-computed KPI correctness fixture (every expected value derived
by hand so an analytics regression fails a test instead of showing a wrong
dashboard number), tenant isolation, the AI payload privacy boundary, RBAC
permission matrix + privilege-escalation guard, and ingestion validator edge
cases (currency/percent parsing, bad dates, duplicate keys, atomic batch
rejection).

## Known limitations / placeholders

Everything below is a deliberate, documented scope boundary — not an
unfinished stub:

- **Member invites don't send email.** `POST /orgs/members` returns a
  one-time temporary password in the API response for the admin to relay
  out-of-band, instead of emailing an invitation link. Wiring a transactional
  email provider was out of scope for a zero-external-account build.
- **AI narrative without a Grok key is template-generated, not model-written.**
  `MockProvider` composes real sentences from your actual computed metrics
  (not lorem ipsum), and every such response — in the UI, the PDF, and the
  PPTX — is explicitly labelled as offline/placeholder output.
- **A user belongs to exactly one organization.** Multi-workspace membership
  (one human, several tenants) would need a join table and an "active
  workspace" concept in the token; deliberately out of scope for this build.
- **Analysis-run caching is time-based, not event-based.** Repeated dashboard
  loads with an identical filter set reuse a run computed within the last 5
  minutes rather than being invalidated precisely on new data arriving.

## Deployment

Local: `docker compose up`. Production: Vercel (frontend) + Render (backend,
Dockerfile-based) + Neon (Postgres). Config files (`frontend/vercel.json`,
`render.yaml`, both Dockerfiles) are committed and ready; no accounts were
created and nothing was deployed as part of this build. See
[SETUP_REQUIRED.md](./SETUP_REQUIRED.md) for the exact steps and the complete
list of what you need to bring.

## Design decisions worth knowing

- **Money is `Decimal` end-to-end**, never `float`, until the API response
  boundary (`app/services/analytics/numeric.py`). Revenue and profit sums are
  exact; only the final JSON-facing rounding to 2dp uses a float.
- **Order lines denormalise region/segment/category onto the fact table**
  rather than joining dimensions at query time — the whole analytics engine
  is a single filtered projection query, which is what lets one `AnalysisRun`
  drive KPIs, breakdowns, anomaly detection and the AI payload from one
  fetch.
- **Anomaly detection runs two detectors together**: Isolation Forest (catches
  unusual *combinations*, like normal revenue with collapsed margin) and a
  robust modified z-score rule per metric (resistant to the very outliers it's
  looking for). Both are seeded and fully deterministic.
- **RFM cluster labels are stable across runs** by ranking K-means clusters on
  mean RFM score before naming them ("Champions", "Loyal", ...) rather than
  trusting scikit-learn's arbitrary integer cluster ids.
