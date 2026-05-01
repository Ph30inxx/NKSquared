from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


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
