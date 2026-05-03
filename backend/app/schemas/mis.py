from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MisStatus = Literal[
    "Pending",
    "Submitted",
    "Under Review",
    "Approved",
    "Rejected",
    "Resubmission Required",
]


class MisSubmissionCreate(BaseModel):
    company_id: str = Field(min_length=1, max_length=20)
    period_year: int = Field(ge=2000, le=2100)
    period_month: int = Field(ge=1, le=12)
    fiscal_year: str | None = Field(default=None, max_length=10)
    notes: str | None = None


class MisSubmissionRejectRequest(BaseModel):
    reason: str = Field(min_length=1)


class MisSubmissionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: str
    period_year: int
    period_month: int
    fiscal_year: str
    status: str
    source_file_name: str | None
    uploaded_at: datetime | None
    uploaded_by: int | None
    reviewed_at: datetime | None
    reviewed_by: int | None
    rejection_reason: str | None
    anomaly_count: int


class MisSubmissionResponse(MisSubmissionListItem):
    source_file_url: str | None
    notes: str | None


class PaginatedMisSubmissions(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MisSubmissionListItem]


class MisSubmissionPreviewRow(BaseModel):
    month_date: date
    geography: str
    revenue_lacs: Decimal | None = None
    cogs_lacs: Decimal | None = None
    gross_margin_lacs: Decimal | None = None
    ebitda_lacs: Decimal | None = None


class MisSubmissionPreview(BaseModel):
    template: str
    monthly_count: int
    bu_count: int
    outlet_count: int
    sample_monthly: list[MisSubmissionPreviewRow]
