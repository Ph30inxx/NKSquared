from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReminderType = Literal[
    "MIS_MONTHLY", "MIS_QUARTERLY", "VALUATION_REVIEW", "CUSTOM"
]


class ReminderScheduleBase(BaseModel):
    company_id: int
    reminder_type: ReminderType = "MIS_MONTHLY"
    enabled: bool = True
    cadence_days: int = Field(default=7, ge=1, le=365)
    first_reminder_offset_days: int = Field(default=5, ge=0, le=365)
    escalation_threshold: int = Field(default=3, ge=1, le=20)
    escalation_contact_id: int | None = None


class ReminderScheduleCreate(ReminderScheduleBase):
    pass


class ReminderScheduleUpdate(BaseModel):
    reminder_type: ReminderType | None = None
    enabled: bool | None = None
    cadence_days: int | None = Field(default=None, ge=1, le=365)
    first_reminder_offset_days: int | None = Field(default=None, ge=0, le=365)
    escalation_threshold: int | None = Field(default=None, ge=1, le=20)
    escalation_contact_id: int | None = None


class ReminderScheduleResponse(ReminderScheduleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ReminderLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    schedule_id: int | None
    company_id: int
    sent_at: datetime
    channel: str
    recipient_email: str | None
    subject: str | None
    status: str
    is_escalation: bool
    related_period: str | None


class PaginatedReminderLogs(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ReminderLogResponse]


class SendNowRequest(BaseModel):
    is_escalation: bool = False
