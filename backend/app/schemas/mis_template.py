from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


METRIC_CODES_MONTHLY: tuple[str, ...] = (
    "revenue_lacs",
    "indirect_income_lacs",
    "total_income_lacs",
    "cogs_lacs",
    "gross_margin_lacs",
    "gross_margin_pct",
    "total_operating_costs_lacs",
    "manpower_cost_lacs",
    "rent_lacs",
    "utilities_lacs",
    "electricity_lacs",
    "channel_expenses_lacs",
    "commission_lacs",
    "transport_lacs",
    "marketing_lacs",
    "admin_lacs",
    "it_lacs",
    "professional_fees_lacs",
    "compliance_costs_lacs",
    "events_lacs",
    "ebitda_lacs",
    "ebitda_pct",
    "itc_reversal_lacs",
    "ebitda_with_itc_lacs",
)


class MisRowMapping(BaseModel):
    label_regex: str = Field(min_length=1, max_length=200)
    metric_code: str = Field(min_length=1, max_length=64)
    geography: str | None = Field(default="consolidated", max_length=30)
    bu_id: str | None = Field(default=None, max_length=20)
    label_col_index: int = Field(default=1, ge=0, le=20)


class MisTemplateBase(BaseModel):
    company_id: str | None = Field(default=None, max_length=20)
    name: str = Field(min_length=1, max_length=80)
    is_default: bool = False
    sheet_name_pattern: str | None = Field(default=None, max_length=120)
    header_row: int = Field(default=1, ge=1, le=200)
    period_orientation: Literal["columns", "rows"] = "columns"
    row_mappings: list[MisRowMapping] = Field(default_factory=list)


class MisTemplateCreate(MisTemplateBase):
    pass


class MisTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    is_default: bool | None = None
    sheet_name_pattern: str | None = Field(default=None, max_length=120)
    header_row: int | None = Field(default=None, ge=1, le=200)
    period_orientation: Literal["columns", "rows"] | None = None
    row_mappings: list[MisRowMapping] | None = None


class MisTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: str | None
    name: str
    version: int
    is_default: bool
    sheet_name_pattern: str | None
    header_row: int
    period_orientation: str
    row_mappings: list[dict[str, Any]]
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class TemplateCandidateRow(BaseModel):
    row_index: int
    label: str
    sample_values: list[Any]


class TemplateCandidatesResponse(BaseModel):
    sheet_names: list[str]
    selected_sheet: str
    header_row: int
    period_columns: list[dict[str, Any]]  # [{col_index, month_date}]
    rows: list[TemplateCandidateRow]


class TemplateDryRunRow(BaseModel):
    month_date: str
    geography: str
    revenue_lacs: str | None = None
    cogs_lacs: str | None = None
    gross_margin_lacs: str | None = None
    ebitda_lacs: str | None = None


class TemplateDryRunResponse(BaseModel):
    monthly_count: int
    bu_count: int
    sample_monthly: list[TemplateDryRunRow]
    period_year: int
    period_month: int
