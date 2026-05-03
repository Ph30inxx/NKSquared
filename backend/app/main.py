from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    auth,
    companies,
    dashboards,
    forex,
    health,
    mis,
    transactions,
    users,
    valuations,
)

app = FastAPI(title="NKSquared Platform API", version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(valuations.router, prefix="/api/v1")
app.include_router(forex.router, prefix="/api/v1")
app.include_router(mis.router, prefix="/api/v1")
app.include_router(dashboards.router, prefix="/api/v1")
