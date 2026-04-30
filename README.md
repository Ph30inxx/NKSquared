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
