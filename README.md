# NKSquared Investment Intelligence Platform

Scaffolded skeleton of the platform described in
`NKSquared_Implementation_Plan_final.docx` (the source of truth for the
actual application). This commit only stands up the dev environment —
no business logic, models, or UI yet.

## What's here

- `backend/` — FastAPI 0.115 + SQLAlchemy 2 + Alembic, exposing `GET /api/v1/health`.
- `frontend/` — React 18 + Vite + TypeScript, single placeholder page that pings the backend health endpoint.
- `docker-compose.yml` — Postgres 16 (with pgvector), Redis 7, the API, a Celery worker, Celery Beat, and the Vite dev server.

The chatbot service (Sprint 9 in the plan) is not scaffolded yet.

## Prerequisites

- Docker & Docker Compose v2
- (Optional, for bare-metal frontend dev) Node 20+

## Bring it up

```bash
cp .env.example .env
docker compose up --build
```

Then:

- API health → http://localhost:8000/api/v1/health
- Frontend  → http://localhost:5173
- Postgres  → `localhost:5432` (user `nksquared_user`, db `nksquared`, password `dev`)

## Useful one-offs

```bash
# Run an Alembic command against the running DB
docker compose run --rm api alembic current
docker compose run --rm api alembic revision --autogenerate -m "msg"

# Tail logs for one service
docker compose logs -f api
```

## Bootstrap admin & log in (Sprint 1)

The platform uses an admin-invite flow — there is no public sign-up. After
bringing the stack up, apply migrations and create the first admin:

```bash
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.cli create-admin \
    --email admin@nksquared.com --password changeme --name "Admin"
```

Then visit http://localhost:5173, sign in with those credentials, and you'll
land on an empty dashboard. Authenticated admins can invite further users by
POST'ing to `/api/v1/users` with a bearer token.

## Try it: portfolio + MOIC (Sprint 2)

Once logged in, click **Portfolio** in the sidebar:

1. **New company** → name it "Acme", set Vehicle = `Strategic_Equity`, Asset class
   = `Direct_Equity`, Status = `Active`, Currency = `INR`, Current value (₹Cr) = `120`.
2. Open the company → **Add transaction** → `Investment`, ₹100 Cr, today's date.
3. **Add transaction** → `Partial_exit`, ₹30 Cr, today's date.
4. The MOIC card now reads **1.50x** — i.e. `(120 + 30) / 100`.

Backend tests for the MOIC engine:

```bash
docker compose run --rm api pytest app/tests -q
```

## Try it: multi-currency, valuations, IRR (Sprint 3)

The Sprint 3 migration seeds two years of monthly USD/AED/EUR → INR rates so the
demo doesn't depend on an external feed. Picking up where Sprint 2 left off:

1. **Add a USD transaction** without filling the FX rate field (e.g. `Investment`,
   USD 10, last quarter). The backend looks up the daily rate from `forex_rates`
   and the row's INR amount populates automatically.
2. **Add a transaction in an un-seeded currency** (e.g. AUD). The INR cell
   shows `—` and the Performance card surfaces a "Recompute FX rates" button.
3. As an **admin**, open **FX rates** in the sidebar → **Add rate** for that
   currency → return to the company → click **Recompute FX rates**. The row
   joins MOIC, IRR refreshes.
4. **Add a valuation** (e.g. post-money ₹2000 Cr). Set `shareholding_pct` on at
   least one transaction first, then click the green check on the valuation row
   to **Mark current**. `current_value_cr` updates pro-rata
   (`post_money × latest_shareholding_pct`). MOIC and IRR refresh.

Daily FX loader is wired to Celery Beat as a stub
(`app.tasks.fx_loader.fetch_daily_rates`); it logs a TODO until a real provider
is wired up. The doc anticipates this with `FX_PROVIDER='manual'` (§ 8.3).

## Try it: Excel grid (Sprint 4)

Sidebar → **Grid** opens an AG Grid Community view of every active company.

- Edit `Company`, `Sector`, `Vehicle`, `Status`, `Country`, `First invest`, or
  `Current (₹Cr)` directly inline. Tab away to commit; a Saved snackbar pops.
  `Invested`, `MOIC`, and `IRR` refresh from the server response.
- Computed columns (Invested / MOIC / IRR) are read-only.
- `Ctrl+C` / `Ctrl+V` work for clipboard interop with Excel. Range-select a
  block and drag the fill handle to propagate values (AG Grid v31 Community).
- A failed save (e.g. an invalid enum) reverts the cell and surfaces the
  validation message.

## Load the sample portfolio

The `samples/` directory is mounted read-only into the api container at
`/samples`. To wipe the demo rows and ingest every sample workbook:

```bash
docker compose run --rm api python -m app.cli load-samples
```

Expected output (counts vary slightly with sheet edits):

```
parsed 50 companies
parsed 36 monthly + 12 bu rows  (Company_01 MIS)
parsed 12 monthly + 117 bu rows (Company_02 MIS)
wiped N existing rows
loaded 50 companies, 75 transactions, 35 valuations, 2 MIS submissions, 48 mis_monthly + 129 mis_bu rows
```

After running:

- `/portfolio` and `/grid` show all 50 companies. `Company_04` (multi-tranche)
  has MOIC ≈ 1.43x and IRR ≈ 35%, matching the source spreadsheet.
- Realised companies (`Company_60` IPO, `Company_29D` matured) are loaded
  with their historical investment tranches; their `investment_status`
  reflects the exit. No synthetic exit cash flow is fabricated — add one
  manually once you have the actual proceeds.
- Two `mis_submissions` are inserted: `Company_01` (canonical doc § 3.3
  layout — full P&L, geographies, BUs) and `Company_02` (non-standard layout,
  monthly revenue + per-BU revenue only — the rest is left NULL until
  Sprint 5's template builder lifts it).

Use `--no-reset` to append to existing rows; default `--reset` truncates
portfolio + MIS tables first. Forex rates, users, and audit_log are
preserved across runs.

## Try the MIS intake (Sprint 5)

Sidebar → **MIS** opens the Inbox. The two pre-loaded `Approved` rows from
`load-samples` show up there alongside any new uploads.

To exercise the upload-then-approve flow on a fresh period:

1. Click **+ New submission** → company `company_99`, period 2025-04, attach
   `samples/Company_01_Mock MIS_FY26.xlsx`.
2. Status flips Pending → Submitted.
3. Open the detail page → click **Refresh preview** → see
   `template=v1, monthly_count=36, bu_count=12` plus 5 sample rows.
4. Click **Approve** → status flips to Approved → 36 `mis_monthly` rows are
   inserted with the new submission id.

Negative paths:

- Re-creating the same `(company, period)` returns **409**.
- Uploading a non-xlsx file or a workbook that doesn't contain
  `Consolidated MIS FY 2026` or `MIS Report FY25-26` returns **422**
  "Template not recognized" at the preview step.
- The Reject dialog requires a reason; rejecting sets `status=Rejected` and
  inserts no `mis_monthly` rows.

Files land at `./data/mis_uploads/<submission_id>.xlsx` on the host
(mounted into the api + worker containers as `/data`).

## Project layout

```
backend/   FastAPI platform API
frontend/  React + Vite SPA
samples/   Local-only reference spreadsheets (gitignored)
```

## Next steps

Sprint 1 of the plan: users / companies / transactions / valuations
schema, JWT auth, login page. See
`NKSquared_Implementation_Plan_final.docx` § 10.
