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
