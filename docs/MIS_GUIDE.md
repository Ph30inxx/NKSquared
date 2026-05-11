# MIS Guide — NKSquared Investment Intelligence Platform

> A from-scratch tour of the **Management Information System (MIS)** module.
> Read it top to bottom if you're new to MIS, or jump to a section using the
> table of contents.

## Table of contents

1. [What is MIS?](#1-what-is-mis)
2. [Vocabulary cheat sheet](#2-vocabulary-cheat-sheet)
3. [The MIS data model](#3-the-mis-data-model)
4. [The submission lifecycle](#4-the-submission-lifecycle)
5. [Feature reference](#5-feature-reference)
   - 5.1 [MIS Inbox](#51-mis-inbox)
   - 5.2 [New submission + file upload](#52-new-submission--file-upload)
   - 5.3 [Preview](#53-preview)
   - 5.4 [Anomaly detection](#54-anomaly-detection)
   - 5.5 [Approve / Reject](#55-approve--reject)
   - 5.6 [Templates: list, build, dry-run, default, delete](#56-templates-list-build-dry-run-default-delete)
   - 5.7 [Bulk export](#57-bulk-export)
   - 5.8 [Analytics endpoints — timeseries & summary](#58-analytics-endpoints--timeseries--summary)
   - 5.9 [Reminders (Celery)](#59-reminders-celery)
   - 5.10 [Public unauthenticated upload](#510-public-unauthenticated-upload)
6. [End-to-end walkthrough (the happy path)](#6-end-to-end-walkthrough-the-happy-path)
7. [Cheat sheets & reference tables](#7-cheat-sheets--reference-tables)
8. [The AI layer — chat, voice, AI dashboards](#8-the-ai-layer--chat-voice-ai-dashboards)
   - 8.1 [Why the AI layer exists & how it fits in](#81-why-the-ai-layer-exists--how-it-fits-in)
   - 8.2 [The MIS tools — what the AI can compute](#82-the-mis-tools--what-the-ai-can-compute)
   - 8.3 [Text chat](#83-text-chat--post-chat)
   - 8.4 [Voice queries — Vapi integration](#84-voice-queries--vapi-integration)
   - 8.5 [AI-generated PDF dashboards](#85-ai-generated-pdf-dashboards)

---

## 1. What is MIS?

**MIS** stands for **Management Information System**. In a private-equity /
venture-investing context (which is what NKSquared is built for), an MIS is the
**monthly performance report** that a portfolio company sends to its investors.

A typical MIS for a single company, for a single month, contains:

- A **Profit & Loss (P&L)** statement:
  `Revenue → COGS → Gross Margin → Operating Costs → EBITDA`
- A breakdown of those numbers by **geography** (e.g. India vs. UAE),
  by **business unit (BU)** (e.g. one BU per restaurant brand inside the
  company), and by **sales channel** (dine-in, food-delivery aggregators,
  catering, franchise…).
- For some companies, **outlet-level** detail — one row per restaurant /
  store with revenue, profit, customer count ("covers"), and rent ratios.

NKSquared receives all of this as an **Excel workbook**, one workbook per
company per month. Different portfolio companies use different layouts, so the
platform has to be flexible about how it parses each workbook.

### Why investors collect MIS

- **Track performance vs. plan.** Did the company hit the revenue / EBITDA
  it promised at the last board meeting?
- **Spot underperformers early.** A two-month dip in gross margin is much
  cheaper to fix than a six-month dip.
- **Drive board conversations.** Numbers are the agenda for monthly /
  quarterly board reviews.
- **Justify valuations.** Quarterly mark-to-market valuations need fresh
  operating data behind them.

The whole MIS module is the pipeline that turns a folder of Excel files into
clean, queryable rows — and then back into the dashboards an analyst actually
looks at.

---

## 2. Vocabulary cheat sheet

| Term | Meaning |
|---|---|
| **Submission** | One Excel workbook for one company for one month, plus the metadata around it (status, who uploaded, when reviewed). |
| **Period** | The `(year, month)` the submission covers, e.g. `2026-04`. |
| **Fiscal year** | NKSquared uses the **Indian fiscal year**: April → March. So `April 2025` is in `FY26`. The platform derives this automatically. |
| **Geography** | A regional split inside one company — e.g. `consolidated`, `country_a`, `city_z`. |
| **BU (Business Unit)** | A sub-business inside a company — e.g. one BU per restaurant brand. Tracked in `mis_bu_monthly`. |
| **Outlet** | An individual location (a single restaurant, store, etc.). Tracked in `mis_outlet_monthly`. |
| **Channel** | A sales channel — dine-in, aggregator A / B / D, catering, franchise. Stored as 6 columns on each BU-monthly row. |
| **Lacs vs. Crores** | All MIS metrics are stored in **Lacs** (1 Lac = 100,000 ₹). 1 Crore = 100 Lacs. The portfolio side of the platform uses Crores; the MIS side uses Lacs. Don't mix them up. |
| **MoM** | Month-over-month — the % change between this month and the previous month. |
| **GM%** | Gross Margin percent: `(Revenue − COGS) / Revenue`. |
| **EBITDA%** | EBITDA / Revenue. |
| **Template** | A reusable parsing rule that maps regex labels in an Excel file (e.g. `^Total Revenue$`) to metric columns in the database (e.g. `revenue_lacs`). |
| **Anomaly** | An automatically detected data-quality issue on a submission (e.g. EBITDA flipped sign, channel revenues don't sum to total). |

---

## 3. The MIS data model

Six tables. One submission "fans out" into many rows in the child tables when
it's approved.

```
                       ┌─────────────────────────┐
                       │     mis_templates       │  parsing rules
                       │  (regex → metric_code)  │  (per-company or global)
                       └────────────┬────────────┘
                                    │ template_id
                                    ▼
                       ┌─────────────────────────┐
        upload .xlsx ─►│      mis_submissions    │  one row per
                       │  (company, period, ...) │  (company, period)
                       └────┬────────┬────────┬──┘
                            │        │        │
              ┌─────────────┘        │        └──────────────┐
              │                      │                       │
              ▼                      ▼                       ▼
  ┌────────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
  │    mis_monthly     │  │   mis_bu_monthly     │  │ mis_outlet_monthly  │
  │  P&L per geography │  │  per BU + channels   │  │  per outlet (ops)   │
  └────────────────────┘  └──────────────────────┘  └─────────────────────┘
              │
              │ also fans out to:
              ▼
  ┌────────────────────┐
  │   mis_anomalies    │  data-quality flags
  └────────────────────┘
```

### `mis_submissions` — the upload envelope

> Source: `backend/app/models/mis.py` → `MisSubmission`

One row per `(company_id, period_year, period_month)` (uniqueness enforced).
Holds:

- The status (`Pending` / `Submitted` / `Under Review` / `Approved` /
  `Rejected` / `Resubmission Required`).
- The path to the uploaded `.xlsx` on disk.
- Who uploaded, who reviewed, when, and (if rejected) why.
- A pointer to the parsing **template** that was used.
- A small JSON cache of the last parse result (avoids re-reading the file
  every time you open the detail page).

This is the table the **MIS Inbox** lists.

### `mis_monthly` — consolidated company-level P&L

> Source: `backend/app/models/mis.py` → `MisMonthly`

One row per `(company, month, geography)`. The metric columns (all in **Lacs**)
are roughly the lines of a standard P&L:

| Group | Columns |
|---|---|
| Income | `revenue_lacs`, `indirect_income_lacs`, `total_income_lacs` |
| COGS / margin | `cogs_lacs`, `gross_margin_lacs`, `gross_margin_pct` |
| Operating costs (the 14 lines) | `total_operating_costs_lacs`, `manpower_cost_lacs`, `rent_lacs`, `utilities_lacs`, `electricity_lacs`, `channel_expenses_lacs`, `commission_lacs`, `transport_lacs`, `marketing_lacs`, `admin_lacs`, `it_lacs`, `professional_fees_lacs`, `compliance_costs_lacs`, `events_lacs` |
| EBITDA | `ebitda_lacs`, `ebitda_pct`, `itc_reversal_lacs`, `ebitda_with_itc_lacs` |

If the company reports both India and UAE, you'll see two rows per month here
(one per geography). A `consolidated` row may also be present.

### `mis_bu_monthly` — same metrics per Business Unit

> Source: `backend/app/models/mis.py` → `MisBuMonthly`

One row per `(company, bu_id, month)`. Same revenue / COGS / GM / EBITDA
columns as `mis_monthly`, plus six **channel revenue** columns:

`channel_dine_in_lacs`, `channel_aggregator_a_lacs`,
`channel_aggregator_b_lacs`, `channel_aggregator_d_lacs`,
`channel_catering_lacs`, `channel_franchise_lacs`.

### `mis_outlet_monthly` — outlet-level operational P&L

> Source: `backend/app/models/mis.py` → `MisOutletMonthly`

One row per `(company, outlet, month)`. Adds operational signals on top of the
financials: `area_sqft`, `covers` (number of customers served),
`sales_to_rent_ratio`, plus `revenue_lacs`, `operational_profit_lacs`, and
`operational_profit_pct`.

### `mis_anomalies` — data-quality flags

> Source: `backend/app/models/mis.py` → `MisAnomaly`

Created automatically by the **anomaly detector** when a file is uploaded
or re-approved (see [§5.4](#54-anomaly-detection)). Each row carries the
rule code, severity (`error` / `warning`), a human-readable message, and
context (period, geography, BU) so the UI can surface them inline.

### `mis_templates` — Excel-parsing rules

> Source: `backend/app/models/mis_template.py` → `MisTemplate`

Each template knows: which **sheet** in the workbook to read (regex), which
**header row** to look for period dates in, which **orientation** the periods
are laid out in (today: `columns`), and a **`row_mappings`** JSON list — each
mapping says "if you see a row whose label matches this regex, treat its
values as this metric, optionally for this geography or this BU".

A template can be **company-specific** (`company_id` set) or **global**
(`company_id` is NULL — used as a fallback). Each company can have one
**default** template (`is_default = true`) that gets picked automatically
during upload.

---

## 4. The submission lifecycle

```
            POST /mis/submissions
                    │
                    ▼
              ┌──────────┐
              │ Pending  │  no file uploaded yet
              └────┬─────┘
                   │  POST /mis/submissions/{id}/upload (.xlsx)
                   ▼
              ┌──────────┐                      ┌─────────────────────────┐
              │Submitted │ ◄────────────────────│ Resubmission Required   │
              └────┬─────┘    re-upload         └─────────────────────────┘
                   │
        analyst reviews preview + anomalies
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
  POST /approve         POST /reject (reason)
        │                     │
        ▼                     ▼
  ┌──────────┐           ┌──────────┐
  │ Approved │           │ Rejected │
  └──────────┘           └──────────┘
   ▲    rows written into mis_monthly /
   │    mis_bu_monthly / mis_outlet_monthly
```

| Transition | Endpoint | Required role | Side effects |
|---|---|---|---|
| Create empty submission | `POST /mis/submissions` | ADMIN / ANALYST | Insert row with `status=Pending`. Returns 409 if `(company, period)` already exists. |
| Upload file | `POST /mis/submissions/{id}/upload` | ADMIN / ANALYST | File saved to `./data/mis_uploads/<id>.xlsx`; backend tries to parse and runs the anomaly detector; status flips `Pending → Submitted`. |
| Refresh preview | `GET /mis/submissions/{id}/preview` | any authenticated user | Re-parses the file from disk (does not commit). |
| Approve | `POST /mis/submissions/{id}/approve` | ADMIN / ANALYST | Re-parses the file; **wipes prior child rows for this submission**, inserts fresh rows into `mis_monthly` / `mis_bu_monthly` / `mis_outlet_monthly`; refreshes anomalies; writes audit log. Idempotent — safe to call again after a fix. |
| Reject | `POST /mis/submissions/{id}/reject` | ADMIN / ANALYST | Stores the rejection reason; status flips to `Rejected`. No child rows are written. |

Reads (list, detail, preview, anomalies, analytics) are open to **any
authenticated user**; writes (create, upload, approve, reject) require
**ADMIN** or **ANALYST**. This is enforced in
`backend/app/routers/mis.py` via `require_role(["ADMIN", "ANALYST"])`.

---

## 5. Feature reference

Each feature gets the same three-part treatment: **What → How → Why**.

### 5.1 MIS Inbox

> **Where:** `/mis` — sidebar → **MIS**
> **Frontend:** `frontend/src/pages/mis/MisInboxPage.tsx`
> **Backend:** `GET /mis/submissions` in `backend/app/routers/mis.py`

**What it is.** A paginated table of every MIS submission across the entire
portfolio, with status filters and a company-code search. The "front door" of
the module — every other MIS feature is reachable from here.

**How to use it.**

1. Click **MIS** in the sidebar.
2. Use the **status toggle** (`All / Pending / Submitted / Under Review /
   Approved / Rejected`) to narrow by workflow state.
3. Type a company code (e.g. `company_01`) into the **Company code** filter
   to narrow to a single company.
4. The table shows: `# / Company / Period / FY / Status / File / Uploaded /
   Reviewed`. Status is rendered as a colour-coded chip.
5. Click any row to open that submission's detail page.
6. Pagination at the bottom: 10 / 25 / 50 / 100 rows per page.

The query parameters this page sets on the backend are
`?status=&company_id=&limit=&offset=`.

**Why it exists.** Without an inbox, an analyst has no way to see "what's
pending review across the portfolio right now". The status filter is the
primary triage tool — open it on `Submitted`, work down the list.

---

### 5.2 New submission + file upload

> **Where:** Inbox → **+ New submission** button
> **Frontend:** `MisUploadDialog.tsx`, then `MisDetailPage.tsx`
> **Backend:** `POST /mis/submissions` then
> `POST /mis/submissions/{id}/upload`

**What it is.** A two-step workflow that creates the submission record and
attaches the Excel file in a single user action.

**How to use it.**

1. From the Inbox, click **+ New submission**.
2. In the dialog:
   - Pick the **Company** (autocomplete from your portfolio companies; you
     can also type a freeform company code).
   - Pick **Year** and **Month**. The fiscal year is derived automatically
     (e.g. May 2025 → `FY26`).
   - Choose the **.xlsx file** from your machine. Max 25 MB.
3. Click **Create + upload**. The dialog closes and you land on the
   submission detail page.
4. The backend immediately tries to parse the file:
   - First with the **template_id** you passed (if any).
   - Otherwise the **default template** for that company.
   - Otherwise legacy **v1 / v2** sheet-name heuristics
     (`Consolidated MIS FY 2026`, `MIS Report FY25-26`).
5. The status flips `Pending → Submitted`. Anomalies are detected in the
   background. The preview panel populates.

If you upload a non-`.xlsx` file or a workbook the platform can't recognise,
you'll get a `422 Template not recognized`.
If the same `(company, period)` already exists, you'll get a `409`.

**Why it exists.** Structured intake replaces the "files mailed back and
forth" problem. Every submission gets a stable ID, an audit trail of who did
what when, and a machine-readable preview before any data is committed.

---

### 5.3 Preview

> **Where:** Submission detail page → **Refresh preview** button
> **Backend:** `GET /mis/submissions/{id}/preview`

**What it is.** A non-destructive parse of the uploaded file — the backend
opens the workbook, runs the chosen template against it, and returns:

- The template name that was matched (e.g. `Company_01 Monthly MIS v3`).
- Row counts: how many `mis_monthly`, `mis_bu_monthly`, and
  `mis_outlet_monthly` rows it would produce on approval.
- A 5-row sample table: month, geography, revenue, COGS, gross margin,
  EBITDA.

Nothing is written to the database during a preview.

**How to use it.** On the submission detail page, click **Refresh preview**.
The chip strip updates (`template = …, monthly_count = 36, bu_count = 12,
outlet_count = 0`) and a sample table appears below.

**Why it exists.** It lets the reviewer eyeball whether the parser actually
picked up the right rows — *before* they hit Approve and rows get committed
into the analytics tables. Catching a misaligned template at this stage saves
having to undo an approval later.

---

### 5.4 Anomaly detection

> **Where:** Anomaly panel on the submission detail page
> **Backend:** `backend/app/services/anomaly_detector.py`,
> `GET /mis/submissions/{id}/anomalies`
> **Frontend:** `frontend/src/pages/mis/AnomalyPanel.tsx`

**What it is.** A rules engine that runs after upload and after re-approval,
producing a list of warnings and errors attached to the submission. The
panel on the detail page renders them with an error/warning icon, the metric
context (period / geography / BU), and a human-readable message.

**The 10 rules:**

| Code | Severity | What it means |
|---|---|---|
| `MISSING_REQUIRED_LINE` | error | Revenue, COGS, or EBITDA is NULL on a row that should have it. Usually a template-mapping miss. |
| `ARITHMETIC_GP` | error | Gross Margin ≠ Revenue − COGS (within 1% tolerance). The arithmetic in the workbook doesn't add up. |
| `FUTURE_DATED_ROW` | error | A row's month is in the future (typo in the period header). |
| `UNIT_MISMATCH` | error | Revenue > 100,000 Lacs — almost certainly the file is in Crores or raw ₹ instead of Lacs. |
| `CHANNEL_SUM_MISMATCH` | warning | On a BU row, the six channel-revenue columns don't add up to total revenue (within 1%). |
| `MOM_REVENUE_SWING` | warning | Revenue moved more than 30% versus the prior month. Worth a sanity check. |
| `MOM_EBITDA_FLIP` | warning | EBITDA changed sign with magnitude >20%. Big swings deserve a comment. |
| `GM_DRIFT` | warning | Gross margin % drifted more than 5 percentage points from the trailing-3-month average. |
| `FX_RATE_STALE` | warning | A foreign-currency row was used but no FX rate exists within the last 30 days. |
| `DUPLICATE_SUBMISSION` | error | Another **approved** submission already exists for the same `(company, period)`. |

**How to use it.** You don't trigger anomalies manually — they appear
automatically. On the detail page, the **Anomalies** panel sits above the
metadata and shows the count of errors and warnings as chips, then lists
each one. Errors are advisory, not blocking — you can still hit Approve, but
the anomaly count is recorded on the submission so the Inbox can flag it
later.

**Why it exists.** A quality gate. Without these rules, a single typo
("revenue in Crores instead of Lacs") would silently propagate into every
chart and KPI on the platform. The split between `error` and `warning` lets
the analyst know what's "stop and fix" versus "note and move on".

---

### 5.5 Approve / Reject

> **Where:** Submission detail page → **Approve** / **Reject** buttons
> **Backend:** `POST /mis/submissions/{id}/approve`,
> `POST /mis/submissions/{id}/reject`

**What it is.** The human checkpoint between "raw upload" and "trusted data
in analytics".

**Approve.** One click. Behind the scenes:

1. The file is re-parsed (more thoroughly than the upload-time parse).
2. **All prior child rows for this submission are deleted** from
   `mis_monthly` / `mis_bu_monthly` / `mis_outlet_monthly` — this makes
   approval **idempotent**, so re-approving after a fix is safe.
3. Fresh rows are inserted.
4. Anomalies are re-detected and the submission's `anomaly_count` is updated.
5. Status flips to `Approved`; an audit log entry is written.

**Reject.** Opens a dialog asking for a **reason** (required, multiline).
On confirm:

1. Status flips to `Rejected`.
2. The reason is stored on the submission.
3. **No** rows are written into the analytics tables.

The detail page then shows the rejection reason in a red alert at the top.
The portfolio company can re-upload by creating a new submission for the
same period (or by using a public-upload link, see [§5.10](#510-public-unauthenticated-upload)).

**Why it exists.** Explicit human approval is the boundary between "raw
upload that may have errors" and "trusted data that drives MoM charts and
board packs". Idempotent re-approval means an analyst who finds a typo can
fix it in the source workbook, re-upload, and re-approve without manual
cleanup of the child tables.

---

### 5.6 Templates: list, build, dry-run, default, delete

> **Where:** `/mis/templates` — sidebar → **MIS Templates** (or Inbox →
> **Templates** button)
> **Frontend:** `MisTemplateListPage.tsx`, `MisTemplateBuilderPage.tsx`
> **Backend:** `backend/app/routers/mis_templates.py`

**What it is.** The system that lets you parse different companies' Excel
layouts without writing any code. Each template is a JSON spec
(`row_mappings`) that says "this regex on this row maps to this metric".

#### Listing templates

The list page shows: `# / Name / Company / Sheet pattern / Mappings (count)
/ Version / Default / Actions`. Templates with `company_id = NULL` are
labelled **Global** and are used as a fallback when a company has no
specific template. Click the **star** in the *Default* column to toggle
`is_default` for that template (only one template per company can be
default).

#### Building a template — the 3-step builder

> Click **+ New template** in the list page (or click an existing row to
> edit it).

**Step 1 — Upload sample file & metadata.**

- **Template name** (e.g. `Company_03 Monthly MIS`).
- **Company code** (optional; leave empty for a Global fallback template).
- **Sheet name pattern** — a regex like `^MIS Report.*$`. If you leave it
  blank, the first sheet in the workbook is used.
- **Header row** — the 1-based row in the sheet that contains the period
  date headers. Default is `2`.
- **Set as default for company** — toggles `is_default`.
- Pick a sample `.xlsx` and click **Extract row labels**.

The backend reads the workbook and shows you:

- The list of sheet names and which one was selected.
- The list of period columns it found in the header row.
- A table of **candidate rows** — every row that has a non-empty label,
  with its row index and a couple of sample values.

**Step 2 — Map rows to metrics.**

- For each candidate row that you want to capture, click **Map**. That
  creates a new mapping with a default regex (the row label, escaped) and a
  default metric (`revenue_lacs`).
- Edit the mapping inline:
  - **Regex** — what label should match. Tighten it if needed
    (e.g. `^Total Revenue$`).
  - **Metric** — pick from the 24 metric codes (`revenue_lacs`, `cogs_lacs`,
    `gross_margin_lacs`, `manpower_cost_lacs`, `rent_lacs`, …,
    `ebitda_lacs`, `ebitda_pct`, etc.).
  - **Geography** — `consolidated` by default, or a specific region.
  - **BU** — set if this row is for a specific business unit.
- Add as many mappings as you need. Delete any you don't want.

**Step 3 — Verify and save.**

- Click **Create & dry-run** (or **Save & dry-run** when editing).
- The template is saved, then **dry-run** against the file you uploaded —
  but **nothing is committed** to `mis_monthly` / `mis_bu_monthly`. You see:
  - Row counts (monthly, BU, latest period).
  - A sample table with month / geography / revenue / COGS / GM / EBITDA.
- If the parse fails, you get a 422 with an error message and you can fix
  the regex / mapping before saving.
- Click **Done** to return to the list page.

#### Other template actions

- **PATCH a template** — edits like adding mappings auto-bump
  `version`. A new version invalidates any cached parse on existing
  submissions.
- **POST `/mis/templates/{id}/set-default`** — same as clicking the star.
  Clears `is_default` on every other template for the same company.
- **DELETE `/mis/templates/{id}`** — returns 409 if any submission still
  references the template; otherwise removes it.

**Why it exists.** Portfolio companies don't all use the same Excel layout
— one might call the row "Total Revenue", another "Net Sales". Hard-coding a
parser per layout would mean a code release every time a new company joins.
Templates put that customisation in the database, behind a UI that an
operations user can drive without touching code. The dry-run-before-save
flow prevents broken templates from silently failing future approvals.

---

### 5.7 Bulk export

> **Where:** Inbox → **Bulk export** button
> **Frontend:** `BulkExportDialog.tsx`, `frontend/src/api/exports.ts`
> **Backend:** `POST /exports/mis/bulk.xlsx`
> (and `GET /exports/mis/{company_id}.xlsx` for a single company)

**What it is.** A way to pull the approved MIS data for many companies into
one Excel workbook in one click.

**How to use it.**

1. From the Inbox, click **Bulk export**.
2. Type or paste company codes — space- or comma-separated, e.g.
   `company_01 company_02 company_03`. Press Enter or click **Add**.
3. Each code appears as a removable chip.
4. Click **Download (N)**.
5. Your browser downloads `mis_bulk_YYYYMMDD.xlsx`.

The single-company variant is `GET /exports/mis/{company_id}.xlsx` — handy
if you only need one company.

**Required role:** ADMIN, ANALYST, or VIEWER (i.e. anyone authenticated).

**Why it exists.** Board packs, LP reports, and ad-hoc analysis routinely
need data from many portfolio companies side-by-side. Doing it one download
at a time is tedious; the bulk endpoint produces a single workbook with one
sheet (or one section) per company.

---

### 5.8 Analytics endpoints — timeseries & summary

> **Backend:** `backend/app/services/timeseries_service.py`,
> last two endpoints in `backend/app/routers/mis.py`

These two endpoints are **how charts get their data** on the company detail
page (and elsewhere). They're not directly exposed as a button on the MIS
pages — they're consumed by the rest of the UI.

#### `GET /mis/companies/{company_code}/timeseries`

**What it returns.** A time-series of monthly metrics for one company, with
**month-on-month % change** annotated on each point.

**Query parameters.**

| Param | Default | What it does |
|---|---|---|
| `metrics` | `revenue_lacs,cogs_lacs,gross_margin_lacs,ebitda_lacs,gross_margin_pct` | Comma-separated list of which metric columns to return. |
| `from` | 24 months ago | Inclusive lower bound, `YYYY-MM`. |
| `to` | latest month | Inclusive upper bound, `YYYY-MM`. |
| `breakdown` | `none` | `none` = consolidated; `geography` = nested per-geography series; `channels` = BU-level channel mix. |

**Response shape.**

```jsonc
{
  "company_code": "company_01",
  "months": ["2024-04-01", "2024-05-01", ...],
  "series": {
    "revenue_lacs": [
      {"month": "2024-04-01", "value": 412.55, "mom_pct": null},
      {"month": "2024-05-01", "value": 438.10, "mom_pct": 6.19},
      ...
    ],
    "ebitda_lacs": [...]
  }
}
```

**Why it exists.** This is the single endpoint that drives every line chart
on the company detail view. The breakdown options let one endpoint power
both consolidated views and per-geography / per-channel deep-dives.

#### `GET /mis/companies/{company_code}/summary`

**What it returns.** The company detail dashboard payload — KPIs for the
latest period, a P&L waterfall, the BU breakdown, the channel mix, and a
pointer to the latest submission and its anomaly count.

**Response shape (abbreviated).**

```jsonc
{
  "latest_month": "2026-03-01",
  "latest_submission_id": 42,
  "anomaly_count": 3,
  "kpis": {
    "revenue":      {"value": 512.4, "prev_value": 478.1, "mom_pct": 7.18},
    "cogs":         {"value": 198.2, "prev_value": 187.0, "mom_pct": 5.99},
    "gross_margin": {"value": 314.2, "prev_value": 291.1, "mom_pct": 7.93},
    "ebitda":       {"value":  43.5, "prev_value":  35.2, "mom_pct": 23.58}
  },
  "waterfall": [
    {"label": "Revenue",      "value":  512.4, "kind": "start"},
    {"label": "COGS",         "value": -198.2, "kind": "negative"},
    {"label": "Gross Margin", "value":  314.2, "kind": "subtotal"},
    {"label": "OpEx",         "value": -270.7, "kind": "negative"},
    {"label": "EBITDA",       "value":   43.5, "kind": "end"}
  ],
  "bu_breakdown":  [...],
  "channel_mix":   {...}
}
```

Returns `404` if the company has no MIS data yet.

**Why it exists.** The company detail page would otherwise have to make
several different API calls and stitch them together client-side. The
summary endpoint answers "what does this company look like right now?" in a
single round trip.

---

### 5.9 Reminders (Celery)

> **Backend:** `backend/app/tasks/reminders.py`
> **Templates:** `backend/app/templates/email/first_reminder.html.j2`,
> `escalation.html.j2`

**What it is.** A background job that nudges portfolio companies to submit
their MIS on time, and escalates if they don't.

**How it runs.** Celery Beat fires `check_pending_mis()` once an hour. The
task:

1. Loads every active company with a Monthly reporting frequency.
2. Decides which reminder schedules are due (based on the day-of-month
   logic in the schedule).
3. Enqueues `send_reminder(schedule_id, is_escalation)` tasks.
4. The send-reminder task renders one of two Jinja2 email templates
   (`first_reminder.html.j2` for the initial nudge, `escalation.html.j2`
   for overdue submissions) with the company / period context, and
   dispatches the email.

**Why it exists.** Without automated reminders, an analyst would have to
chase 50+ companies manually every month. The two-tier (first reminder →
escalation) cadence matches the rhythm most investor-relations teams
already follow.

---

### 5.10 Public unauthenticated upload

> **Where:** `/upload/:token` (no login required)
> **Frontend:** `frontend/src/pages/public/PublicUploadPage.tsx`
> **Backend:** `backend/app/routers/public_upload.py` —
> `GET /public/upload/verify`, `POST /public/upload`

**What it is.** A tokenised, login-less upload page that a portfolio
company's CFO can use to drop their `.xlsx` directly into the platform
without needing a NKSquared account.

**How it flows.**

1. An analyst (or an automated process — see reminders above) generates a
   token for a `(company, period)` pair and emails it to the contact at the
   portfolio company.
2. The contact opens `/upload/<token>` in a browser.
3. The page calls `GET /public/upload/verify` with the token, which returns
   the company name, the period, and how many days until the link expires.
4. The contact selects an `.xlsx` and clicks **Upload**.
5. Frontend POSTs to `/public/upload`. On success they see "Thanks — file
   received". A submission is created (or an existing one updated) on the
   platform side, and it shows up in the MIS Inbox like any other.

**Why it exists.** Demanding a platform account for every portfolio
company's finance lead just to deliver one file a month is friction that
delays the data. A short-lived tokenised link gets the file in without
anyone touching the user-management flows.

---

## 6. End-to-end walkthrough (the happy path)

This walks you through a full submission using the seeded sample workbook.
You should be able to follow it on a fresh dev environment.

### Pre-requisites

Bring the stack up and seed the demo data:

```bash
cp .env.example .env
docker compose up --build
docker compose run --rm api alembic upgrade head
docker compose run --rm api python -m app.cli create-admin \
    --email admin@nksquared.com --password changeme --name "Admin"
```

Sign in at http://localhost:5173.

### Step 1 — Open the MIS Inbox

Sidebar → **MIS**. You see whatever submissions already exist. If you ran
`docker compose run --rm api python -m app.cli load-samples`, two
`Approved` rows for `Company_01` and `Company_02` will already be there.

### Step 2 — Create a new submission

- Click **+ New submission**.
- Company code: `company_99` (or any company that doesn't yet have an
  April 2025 submission).
- Year: `2025`, Month: `April`. The fiscal year auto-fills as `FY26`.
- File: `samples/Company_01_Mock MIS_FY26.xlsx`.
- Click **Create + upload**.

The dialog closes, you land on `/mis/<id>`, and the status reads
`Submitted`.

*Why each input?* The `(company, period)` pair is what makes a submission
unique — uploading the same file twice for the same month is blocked by
default (you'd get a 409). The fiscal year matters because every analytics
endpoint groups data by FY (Indian Apr–Mar).

### Step 3 — Refresh the preview

Click **Refresh preview**. You'll see something like:

```
template = v1   monthly_count = 36   bu_count = 12   outlet_count = 0
```

…and a 5-row sample table showing Apr-25, May-25, … values for revenue,
COGS, GM, EBITDA.

*Why?* The preview proves the parser actually worked **before** you commit
anything to the analytics tables. If the row counts are wildly off (e.g.
`monthly_count = 0`), stop and check that the right template was matched —
you may need to set up a per-company template (§5.6) instead.

### Step 4 — Review anomalies

Scroll up to the **Anomalies** panel. The sample workbook is well-formed,
so you should mostly see warnings (`MOM_REVENUE_SWING`, `GM_DRIFT`) rather
than errors. If you see an error like `MISSING_REQUIRED_LINE`, fix the
template mapping or the workbook before approving.

*Why?* This is your last chance to catch a typo or a wrong unit before the
data goes live. A red error here usually means "don't approve yet".

### Step 5 — Approve

Click **Approve**.

- Status flips to `Approved`.
- 36 rows land in `mis_monthly`, 12 in `mis_bu_monthly`, 0 in
  `mis_outlet_monthly` (this template doesn't include outlets).
- Anomalies are refreshed. The audit log records the approval.

### Step 6 — See the data flow into analytics

The summary and timeseries endpoints will now return data for that
company:

```bash
curl -H "Authorization: Bearer <jwt>" \
     "http://localhost:8000/api/v1/mis/companies/company_99/summary"
```

…which returns the KPIs / waterfall / BU breakdown you'd see on the
company detail view.

### Step 7 — (Optional) Reject and re-approve

To exercise the rejection path:

- Open a `Submitted` submission.
- Click **Reject**, type a reason (e.g. "April revenue doesn't match bank
  statements"), confirm.
- Status → `Rejected`. The reason shows on the detail page.
- The portfolio company re-uploads via a new submission (or via a public
  upload link). Approve that one when ready.

---

## 7. Cheat sheets & reference tables

### Where the code lives

| Layer | Path |
|---|---|
| Backend models | `backend/app/models/mis.py`, `backend/app/models/mis_template.py` |
| Backend routers | `backend/app/routers/mis.py`, `backend/app/routers/mis_templates.py`, `backend/app/routers/exports.py`, `backend/app/routers/public_upload.py` |
| Backend services | `backend/app/services/mis_service.py`, `backend/app/services/anomaly_detector.py`, `backend/app/services/timeseries_service.py`, `backend/app/services/mis/{parser,template_runner,storage}.py` |
| Backend schemas | `backend/app/schemas/mis.py`, `backend/app/schemas/mis_template.py` |
| Backend tasks | `backend/app/tasks/reminders.py` |
| Email templates | `backend/app/templates/email/first_reminder.html.j2`, `escalation.html.j2` |
| Alembic migration | `backend/alembic/versions/c3d4e5f6a7b8_sprint6_mis_anomalies.py` |
| Frontend pages | `frontend/src/pages/mis/{MisInboxPage,MisDetailPage,MisUploadDialog,AnomalyPanel,BulkExportDialog}.tsx`, `frontend/src/pages/mis/templates/{MisTemplateListPage,MisTemplateBuilderPage}.tsx`, `frontend/src/pages/public/PublicUploadPage.tsx` |
| Frontend API clients | `frontend/src/api/{mis,misTemplates,exports}.ts` |
| Chatbot service (separate FastAPI app, port 8001) | `chatbot/server.py`, `chatbot/agents/`, `chatbot/tools/`, `chatbot/voice/`, `chatbot/dashboard/` |
| Frontend AI integration | `frontend/src/features/chatbot/{ChatPage,ChatWidget,VoicePage}.tsx`, `frontend/src/pages/ai-dashboard/AIDashboardPage.tsx` |
| Uploaded files (host) | `./data/mis_uploads/<submission_id>.xlsx` |

### Status reference

| Status | Meaning | Next valid transitions |
|---|---|---|
| `Pending` | Submission created, no file uploaded yet | → `Submitted` (on upload) |
| `Submitted` | File uploaded and parsed | → `Approved`, `Rejected`, `Under Review` |
| `Under Review` | Reviewer has opened it but not decided | → `Approved`, `Rejected` |
| `Approved` | Rows committed to analytics tables | (terminal — re-approval is allowed and idempotent) |
| `Rejected` | Reason recorded, no rows committed | (effectively terminal — file the company sends next becomes a new submission) |
| `Resubmission Required` | Reviewer asked for a redo without an outright reject | → `Submitted` (on re-upload) |

### Anomaly rule reference

| Code | Severity | Plain-English |
|---|---|---|
| `MISSING_REQUIRED_LINE` | error | Revenue / COGS / EBITDA is NULL on a row that should have it. |
| `ARITHMETIC_GP` | error | Gross Margin ≠ Revenue − COGS within 1%. |
| `FUTURE_DATED_ROW` | error | A row's month is in the future. |
| `UNIT_MISMATCH` | error | Revenue > 100,000 Lacs (probably the file is in Crores). |
| `DUPLICATE_SUBMISSION` | error | Another `Approved` submission exists for the same `(company, period)`. |
| `CHANNEL_SUM_MISMATCH` | warning | BU channel revenues don't sum to total revenue (within 1%). |
| `MOM_REVENUE_SWING` | warning | Revenue moved >30% MoM. |
| `MOM_EBITDA_FLIP` | warning | EBITDA changed sign with magnitude >20%. |
| `GM_DRIFT` | warning | GM% drifted >5 pp from trailing-3-month average. |
| `FX_RATE_STALE` | warning | Foreign-currency row but no FX rate within 30 days. |

### MIS API endpoint reference

All paths assume the platform prefix `/api/v1`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `GET`    | `/mis/submissions`                          | any auth          | List submissions (filter: `status`, `company_id`, paginate). |
| `POST`   | `/mis/submissions`                          | ADMIN / ANALYST   | Create a new (empty) submission. |
| `GET`    | `/mis/submissions/{id}`                     | any auth          | Fetch one submission. |
| `POST`   | `/mis/submissions/{id}/upload`              | ADMIN / ANALYST   | Upload `.xlsx` (multipart, max 25 MB). |
| `GET`    | `/mis/submissions/{id}/preview`             | any auth          | Re-parse file and return sample rows. |
| `POST`   | `/mis/submissions/{id}/approve`             | ADMIN / ANALYST   | Commit rows to `mis_monthly` / `mis_bu_monthly` / `mis_outlet_monthly`. |
| `POST`   | `/mis/submissions/{id}/reject`              | ADMIN / ANALYST   | Mark rejected with a reason. |
| `GET`    | `/mis/submissions/{id}/anomalies`           | any auth          | List detected anomalies. |
| `GET`    | `/mis/companies/{code}/timeseries`          | any auth          | Time-series for charts. |
| `GET`    | `/mis/companies/{code}/summary`             | any auth          | Latest-period KPI dashboard. |
| `GET`    | `/mis/templates`                            | any auth          | List templates. |
| `GET`    | `/mis/templates/{id}`                       | any auth          | Get one template. |
| `POST`   | `/mis/templates`                            | ADMIN / ANALYST   | Create template. |
| `PATCH`  | `/mis/templates/{id}`                       | ADMIN / ANALYST   | Update template (auto-bumps version). |
| `POST`   | `/mis/templates/{id}/set-default`           | ADMIN / ANALYST   | Set as default for the template's company. |
| `DELETE` | `/mis/templates/{id}`                       | ADMIN / ANALYST   | Delete (409 if referenced by a submission). |
| `POST`   | `/mis/templates/extract-candidates`         | ADMIN / ANALYST   | Read a sample file and return candidate row labels. |
| `POST`   | `/mis/templates/{id}/dry-run`               | ADMIN / ANALYST   | Test a template against a file without saving. |
| `GET`    | `/exports/mis/{company_id}.xlsx`            | ADMIN / ANALYST / VIEWER | Download single-company MIS workbook. |
| `POST`   | `/exports/mis/bulk.xlsx`                    | ADMIN / ANALYST / VIEWER | Download multi-company MIS workbook. |
| `GET`    | `/public/upload/verify`                     | public (token)    | Verify a public-upload token. |
| `POST`   | `/public/upload`                            | public (token)    | Upload an `.xlsx` against a token. |

### File-on-disk locations

- Uploaded MIS workbooks: `./data/mis_uploads/<submission_id>.xlsx` on the
  host. Mounted into the `api` and `worker` containers as `/data`.
- Sample workbooks (read-only, for demos): `./samples/`. Mounted into the
  `api` container as `/samples`.

### AI / chatbot service endpoint reference

These endpoints are served by the **separate** chatbot FastAPI app, not the
main platform API. In dev they live on container `nksquared_chatbot`, port
`8001`, and the frontend reaches them via the `VITE_CHATBOT_URL` env var.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST`   | `/chat`                    | platform JWT       | Text chat (Server-Sent Events stream). |
| `GET`    | `/conversations`           | platform JWT       | List the user's conversations. |
| `POST`   | `/conversations`           | platform JWT       | Start a new conversation. |
| `GET`    | `/session/{id}/history`    | platform JWT       | Fetch the transcript for a session. |
| `DELETE` | `/conversations/{id}`      | platform JWT       | Delete a conversation. |
| `POST`   | `/voice/session`           | platform JWT       | Mint a voice-call session, return Vapi credentials. |
| `POST`   | `/vapi/server`             | Vapi shared secret | Vapi webhook (tool calls + status updates). |
| `POST`   | `/dashboard/generate`      | platform JWT       | Kick off AI-PDF generation; returns SSE stream. |
| `GET`    | `/dashboard/history`       | platform JWT       | List past PDF dashboards. |
| `GET`    | `/dashboard/{id}/status`   | platform JWT       | Poll a dashboard job. |
| `GET`    | `/dashboard/{id}/download` | platform JWT       | Download the generated PDF. |
| `GET`    | `/health`                  | public             | Liveness probe. |

---

## 8. The AI layer — chat, voice, AI dashboards

Everything before this section described the **data pipeline** for MIS:
how files come in, how they're parsed, how they're approved, and how the
two analytics endpoints turn them back into KPIs and time-series.

This section describes the **interface layer** that sits on top of all of
that — the way analysts actually *ask questions* of the MIS data without
writing SQL or even clicking through the company detail page. There are
three surfaces: text chat, voice chat, and AI-generated PDF dashboards.
All three share the same underlying tools.

### 8.1 Why the AI layer exists & how it fits in

Looking at the data is half the job. Asking *questions* of the data is the
other half:

- "How did Company_02 do last month?"
- "Which BU is largest this quarter?"
- "Build me a 4-page PDF on Company_01 for the next board meeting."

Doing those by hand means knowing the table names, joining
`mis_monthly` against `mis_bu_monthly`, computing MoM%, finding chart
libraries — work the AI layer does on the analyst's behalf.

**Architectural shape.** The chatbot is a **separate FastAPI service**:

| | Main platform API | Chatbot service |
|---|---|---|
| Code | `backend/app/` | `chatbot/` |
| Container | `nksquared_api` | `nksquared_chatbot` |
| Port | `8000` | `8001` |
| Frontend env var | `VITE_API_URL` | `VITE_CHATBOT_URL` |

Both services share the same Postgres database (the chatbot reads
`mis_monthly` / `mis_bu_monthly` / `mis_outlet_monthly` directly via a
connection pool). Write operations from the chatbot route back through
the platform API so existing audit logging and validation are reused.

### 8.2 The MIS tools — what the AI can compute

> **File:** `chatbot/tools/mis.py`

These five tools are the AI's "vocabulary" for talking about MIS. Every
text-chat answer, voice answer, and PDF chart ultimately calls one of
them. Knowing what each one does makes it much easier to predict whether
the AI will be able to answer a given question.

#### `financial_period_resolver(period: str) → {start, end}`

Translates analyst-friendly period strings into ISO date ranges. Accepts:

- Fiscal years: `'FY26'` → `2025-04-01 … 2026-03-31`
- Quarters: `'Q1_FY26'`, `'Q2_FY26'`, …
- Half-years: `'H1_FY26'`, `'H2_FY26'`
- Rolling: `'last_3_months'`, `'last_6_months'`
- Special: `'ytd'` (fiscal-year-to-date), `'latest'` (most recent
  complete month)
- Explicit: `'2025-04-01:2025-06-30'`

Every other MIS tool that takes a `period` argument calls this resolver
internally, so the same shorthand works everywhere.

#### `get_company_trend(company_id, period, geography, granularity)`

A **time-series with MoM annotations**. Returns one row per period inside
the resolved range, each carrying revenue, COGS, gross margin, EBITDA,
the major opex lines (manpower, rent, marketing), plus the *computed*:

- `mom_revenue_change_pct` — revenue % change vs. prior period
- `mom_ebitda_change_lacs` — EBITDA absolute change in Lacs
- An overall trend flag: `improving` / `deteriorating` / `mixed` /
  `insufficient_data`, derived from the last 3 EBITDA points

`granularity` is `monthly` (default) or `quarterly`. `geography` defaults
to `consolidated` and accepts the same values as `mis_monthly.geography`.

> **Example questions that route here:**
> - "What's the revenue trend for Company_02 in FY26?"
> - "Show me Company_01's last 6 months in Country_A."

#### `get_mis_recent_summary(company_id)`

This is the **"summary of recent updates"** capability. It compares the
latest two months (consolidated only) and returns:

- `latest_month`, `prior_month`
- `overall_direction`: `improving`, `deteriorating`, or `mixed`
- `headline_flags`: human-readable bullets — e.g.
  *"Revenue declined 12.3% MoM"*, *"EBITDA worsened by ₹45 Lacs"*
- `metric_changes`: per-metric `current` / `prior` / `change_abs` /
  `change_pct` / `direction` (where `direction` is *flipped* for cost
  metrics — rising rent is `worsened`, not `improved`)

> **Example questions that route here:**
> - "Quick summary of how Company_01 performed last month."
> - "What are the recent updates for Company_02?"
> - "Did Company_02 improve or deteriorate this month?"

#### `get_bu_breakdown(company_id, period)`

Per-Business-Unit revenue, EBITDA, GM%, and the six channel-revenue
columns (dine-in, aggregator A / B / D, catering, franchise) for every
month in the resolved period. Use this for "which BU is biggest", "which
BU is shrinking", or "what's the channel mix for BU_03".

> **Example questions:**
> - "Which BU is largest for Company_02?"
> - "How much of BU_05's revenue comes from aggregators?"

#### `get_outlet_breakdown(period)`

Outlet-level operational P&L for **Company_01 only** (Company_02 doesn't
report at outlet granularity). Returns `outlet_id`, `city`, `bu_id`,
revenue, operational profit (₹ + %), and the operational signals
`sales_to_rent_ratio`, `covers`, `area_sqft`.

> **Example questions:**
> - "Which outlet has the worst sales-to-rent ratio?"
> - "Top 5 outlets by operational profit % last month."

### 8.3 Text chat — `POST /chat`

> **Frontend:** `frontend/src/features/chatbot/ChatPage.tsx`,
> `ChatWidget.tsx`, `useChatSession.ts`, `chatApi.ts`
> **Backend:** `chatbot/server.py`

**What it is.** A streaming chat endpoint backed by a single
"Intelligence Agent" that has the five MIS tools above, plus
portfolio-side tools, plus a small read-only SQL escape hatch for
questions the structured tools can't answer. Responses stream back as
**Server-Sent Events** so the user sees text as it's generated.

**How to use it.**

1. Open the chat widget (or the dedicated chat page) in the frontend.
2. Type a natural-language question.
3. Watch the answer stream back. The agent will often "show its work" —
   "Let me pull up the MIS data for Company_02…" — before answering.
4. Conversations persist. Use `GET /conversations` to list them and
   `GET /session/{id}/history` to load a transcript.

Conversation management endpoints (all on the chatbot service):

| Endpoint | What it does |
|---|---|
| `GET /conversations`        | List the current user's conversations. |
| `POST /conversations`       | Start a new (empty) conversation. |
| `GET /session/{id}/history` | Fetch the message transcript for a session. |
| `DELETE /conversations/{id}`| Delete a conversation. |

**Write operations.** The agent also has tools that **modify data** —
log a transaction, correct an MIS metric, update a company. These are
loaded only when the agent detects write intent in the message. The
write flow is **dry-run-then-confirm**: the agent first replies with a
preview ("I'm about to log a 5 Cr investment in Company_X dated
March 1st — confirm?"). The actual write only happens after the user
confirms in the next turn.

**Why it exists.** Natural-language Q&A is the lowest-friction way to
explore MIS data. An analyst can ask "what's going on with Company_02"
and get an answer faster than they could open the company detail page,
let alone write a SQL query.

### 8.4 Voice queries — Vapi integration

> **Frontend:** `frontend/src/features/chatbot/VoicePage.tsx`,
> `useVoiceCall.ts`
> **Backend:** `chatbot/voice/router.py` —
> `POST /voice/session`, `POST /vapi/server`

**What it is.** The same Intelligence Agent, reachable over a phone
call. **Vapi** (a voice-AI provider) handles speech recognition and text-
to-speech. The chatbot answers the underlying queries.

**The call flow.**

1. User opens the Voice page. Frontend `POST /voice/session` mints a
   call session and returns the Vapi assistant credentials.
2. The Vapi widget opens a call. Vapi transcribes user speech.
3. Each user turn lands on the chatbot's `/vapi/server` webhook as one
   of two tool invocations:
   - `query_investment_data` — read-only question; routes to the
     Intelligence Agent.
   - `execute_investment_action` — write request; Vapi has already
     obtained verbal confirmation by this point, so the agent runs the
     write directly (no extra dry-run round trip).
4. The agent's reply is run through a **response compressor** — strip
   markdown, drop URLs, truncate to 1–4 sentences (longer for
   "summary" / "trend" / "briefing" queries) — before being spoken
   back through Vapi.
5. When the call ends, the transcript is saved to `voice_chat_messages`
   and shows up in the chat sidebar like any other conversation.

**Why it exists.** Hands-free MIS reviews — useful for quick check-ins
during travel, or for analysts who'd rather narrate than type.

### 8.5 AI-generated PDF dashboards

> **Frontend:** `frontend/src/pages/ai-dashboard/AIDashboardPage.tsx`,
> `dashboardApi.ts`
> **Backend:** `chatbot/dashboard/server.py`,
> `chatbot/dashboard/agents/dashboard.py`

**What it is.** A **one-shot** agent that takes a natural-language brief
("Company_02 FY26 performance with channel analysis"), pulls the right
data, renders charts, and assembles a multi-page **PDF** ready to share.
Unlike the chat agent, this one keeps no session state — each generation
is independent.

**The 30 tools the dashboard agent has access to.**

- **Data tools** — all five MIS tools above plus expanded variants
  (`get_cost_breakdown`, `get_channel_breakdown`,
  `get_outlet_profitability`, `get_mis_submission_status`,
  `get_mis_anomaly_summary`) and portfolio-side tools
  (`get_portfolio_summary`, `get_company_detail`, `calculate_irr`,
  `check_portfolio_alerts`, …).
- **Chart tools** — `create_bar_chart`, `create_line_chart`,
  `create_pie_chart`, `create_kpi_cards`, `create_table_image`,
  `create_waterfall_chart`, `create_combo_chart`, `create_scatter_chart`,
  `create_stacked_area_chart`.
- **Assembly tool** — `_compile_dashboard` writes the final PDF to disk
  and stores its path on the dashboard job.

**The flow.**

1. User types a prompt on the AI Dashboard page.
2. Frontend `POST /dashboard/generate` opens an SSE stream. Events:
   `started` → repeated `heartbeat` → final `complete` (with
   `download_url`, `title`, `page_count`, `summary`) or `error`.
3. The dashboard agent decides which data tools to call, then which
   chart tools to invoke, then calls `_compile_dashboard` to render the
   PDF.
4. Frontend either watches the SSE for the `complete` event or polls
   `GET /dashboard/{id}/status` until status is `ready`.
5. User clicks **Download**, which hits
   `GET /dashboard/{id}/download` and returns the PDF.
6. `GET /dashboard/history` lists all past runs for the user.

**Example prompts and what gets generated.**

- *"Portfolio overview for FY26"* — 2–3 pages: KPI cards (MOIC, IRR,
  totals), pie chart of sectors, list of underperformers.
- *"Company_02 performance FY26 with channel analysis"* — 3–4 pages:
  revenue/EBITDA line chart, BU stacked bar, channel-mix pie, KPI cards.
- *"Company_01 outlet performance and alerts"* — 2–3 pages: outlet
  rankings table, revenue-by-outlet bar chart, anomaly callouts.

**Why it exists.** Turning the *"I need a board pack on Company_X by
4pm"* request into a sub-minute task. The output is a real PDF an
analyst can share without further editing.
