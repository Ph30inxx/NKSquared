from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import AuditLogResponse, PaginatedAuditLog
from app.services.audit_service import list_audit

router = APIRouter(prefix="/audit", tags=["audit"])

_reader = require_role(["ADMIN", "ANALYST"])


@router.get("/log", response_model=PaginatedAuditLog)
def get_audit_log(
    entity_type: str | None = Query(None),
    entity_id: int | None = Query(None),
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _user: User = Depends(_reader),
) -> PaginatedAuditLog:
    items, total = list_audit(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return PaginatedAuditLog(
        total=total,
        limit=limit,
        offset=offset,
        items=[AuditLogResponse(**i) for i in items],
    )
