from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import User


def record_audit(
    db: Session,
    *,
    user_id: int | None,
    entity_type: str,
    entity_id: int,
    action: str,
    field_name: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
) -> None:
    """Append an audit_log row. Caller is responsible for the surrounding commit."""
    db.add(
        AuditLog(
            user_id=user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            field_name=field_name,
            old_value=None if old_value is None else str(old_value),
            new_value=None if new_value is None else str(new_value),
            ip_address=ip_address,
        )
    )


def list_audit(
    db: Session,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Paginated audit-log listing joined with users for email display."""
    base = (
        select(AuditLog, User.email)
        .outerjoin(User, AuditLog.user_id == User.id)
    )
    if entity_type:
        base = base.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        base = base.where(AuditLog.entity_id == entity_id)
    if user_id is not None:
        base = base.where(AuditLog.user_id == user_id)
    if action:
        base = base.where(AuditLog.action == action)
    if since is not None:
        base = base.where(AuditLog.occurred_at >= since)
    if until is not None:
        base = base.where(AuditLog.occurred_at <= until)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = db.execute(count_stmt).scalar_one()

    rows = db.execute(
        base.order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()

    items = [
        {
            "id": row.AuditLog.id,
            "user_id": row.AuditLog.user_id,
            "user_email": row.email,
            "entity_type": row.AuditLog.entity_type,
            "entity_id": row.AuditLog.entity_id,
            "action": row.AuditLog.action,
            "field_name": row.AuditLog.field_name,
            "old_value": row.AuditLog.old_value,
            "new_value": row.AuditLog.new_value,
            "ip_address": row.AuditLog.ip_address,
            "occurred_at": row.AuditLog.occurred_at,
        }
        for row in rows
    ]
    return items, total
