from decimal import Decimal

from pydantic import BaseModel


class PortfolioBucket(BaseModel):
    key: str
    invested_cr: Decimal
    current_cr: Decimal
    weighted_moic: Decimal | None
    count: int


class PortfolioSummary(BaseModel):
    total_invested_cr: Decimal
    current_value_cr: Decimal
    weighted_moic: Decimal | None
    company_count: int
    pending_mis_count: int


class DashboardOverview(BaseModel):
    summary: PortfolioSummary
    by_sector: list[PortfolioBucket]
    by_vintage: list[PortfolioBucket]
    by_category: list[PortfolioBucket]
