"""Test fixtures using an in-memory SQLite database.

Sprint 2 services only touch core ORM types (Integer/String/Date/Numeric/Boolean/
Text/DateTime). They don't depend on Postgres-specific features, so SQLite is fine
for unit-testing the MOIC math and the sign convention without a live Postgres.
"""
from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
import app.models  # noqa: F401  — registers all models on Base.metadata


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
