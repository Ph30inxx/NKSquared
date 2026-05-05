from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CompanyAssetClass = Literal["Direct_Equity", "Fund_Investment", "Debt_Instrument"]
CompanyInvestmentStatus = Literal[
    "Active", "Written_off", "Exit_via_IPO", "Exit_via_Share_swap", "Matured"
]
CompanyPortfolioStatus = Literal["Unrealized", "Realized"]


class CompanyBase(BaseModel):
    company_name: str = Field(min_length=1, max_length=100)
    display_name: str | None = Field(default=None, max_length=100)
    portfolio_type: str | None = Field(default=None, max_length=50)
    investment_status: CompanyInvestmentStatus | None = None
    portfolio_status: CompanyPortfolioStatus | None = None
    asset_class: CompanyAssetClass | None = None
    sector: str | None = Field(default=None, max_length=50)
    sub_sector: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=50)
    date_of_first_investment: date | None = None
    current_value_cr: Decimal | None = None
    currency: str = Field(default="INR", min_length=3, max_length=10)
    reporting_frequency: str = Field(default="Monthly", max_length=20)
    primary_contact_name: str | None = Field(default=None, max_length=120)
    primary_contact_email: str | None = Field(default=None, max_length=255)
    escalation_contact_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, max_length=100)
    portfolio_type: str | None = Field(default=None, max_length=50)
    investment_status: CompanyInvestmentStatus | None = None
    portfolio_status: CompanyPortfolioStatus | None = None
    asset_class: CompanyAssetClass | None = None
    sector: str | None = Field(default=None, max_length=50)
    sub_sector: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=50)
    date_of_first_investment: date | None = None
    current_value_cr: Decimal | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    reporting_frequency: str | None = Field(default=None, max_length=20)
    primary_contact_name: str | None = Field(default=None, max_length=120)
    primary_contact_email: str | None = Field(default=None, max_length=255)
    escalation_contact_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class CompanyListItem(BaseModel):
    """Summary row used by both the list page and the AG Grid view."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    display_name: str | None
    company_code: str | None
    portfolio_type: str | None
    investment_status: str | None
    portfolio_status: str | None
    asset_class: str | None
    sector: str | None
    sub_sector: str | None
    country: str | None
    date_of_first_investment: date | None
    investment_value_cr: Decimal | None
    current_value_cr: Decimal | None
    moic: Decimal | None
    irr: Decimal | None
    currency: str
    notes: str | None
    is_active: bool


class CompanyResponse(CompanyListItem):
    reporting_frequency: str
    primary_contact_name: str | None
    primary_contact_email: str | None
    escalation_contact_email: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedCompanies(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[CompanyListItem]
