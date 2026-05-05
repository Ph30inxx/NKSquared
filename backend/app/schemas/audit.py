from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None
    user_email: str | None
    entity_type: str
    entity_id: int
    action: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    ip_address: str | None
    occurred_at: datetime


class PaginatedAuditLog(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditLogResponse]
