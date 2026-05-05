"""Sprint 8 — list_audit pagination and filtering."""
from __future__ import annotations

from datetime import datetime, timezone

from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_service import list_audit, record_audit


def _seed(db) -> tuple[int, int]:
    u1 = User(
        email="alice@example.com",
        full_name="Alice",
        password_hash="x",
        role="ANALYST",
    )
    u2 = User(
        email="bob@example.com",
        full_name="Bob",
        password_hash="x",
        role="ADMIN",
    )
    db.add_all([u1, u2])
    db.commit()

    record_audit(
        db,
        user_id=u1.id,
        entity_type="portfolio_transaction",
        entity_id=1,
        action="CREATE",
        new_value="Investment 5.0 INR",
    )
    record_audit(
        db,
        user_id=u1.id,
        entity_type="portfolio_transaction",
        entity_id=1,
        action="UPDATE",
        field_name="amount",
        old_value="5.0",
        new_value="6.0",
    )
    record_audit(
        db,
        user_id=u2.id,
        entity_type="mis_submission",
        entity_id=42,
        action="APPROVE",
        new_value="template=v1 monthly=12 bu=24",
    )
    db.commit()
    return u1.id, u2.id


def test_list_audit_returns_user_email(db) -> None:
    _seed(db)
    items, total = list_audit(db)
    assert total == 3
    emails = {row["user_email"] for row in items}
    assert emails == {"alice@example.com", "bob@example.com"}


def test_list_audit_filters_by_entity_type(db) -> None:
    _seed(db)
    items, total = list_audit(db, entity_type="mis_submission")
    assert total == 1
    assert items[0]["action"] == "APPROVE"
    assert items[0]["entity_id"] == 42


def test_list_audit_filters_by_action_and_user(db) -> None:
    u1_id, _ = _seed(db)
    items, total = list_audit(db, user_id=u1_id, action="UPDATE")
    assert total == 1
    assert items[0]["field_name"] == "amount"
    assert items[0]["new_value"] == "6.0"


def test_list_audit_pagination(db) -> None:
    _seed(db)
    page1, total = list_audit(db, limit=2, offset=0)
    page2, _ = list_audit(db, limit=2, offset=2)
    assert total == 3
    assert len(page1) == 2
    assert len(page2) == 1
    # Default sort is recent first; the second page yields the oldest (CREATE).
    assert page2[0]["action"] == "CREATE"
