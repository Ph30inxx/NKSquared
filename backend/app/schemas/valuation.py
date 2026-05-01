from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ValuationCreate(BaseModel):
    valuation_date: date
    post_money_valuation_cr: Decimal = Field(gt=0)
    pre_money_valuation_cr: Decimal | None = Field(default=None, gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=10)
    source: str | None = Field(default=None, max_length=64)
    notes: str | None = None


class ValuationUpdate(BaseModel):
    valuation_date: date | None = None
    post_money_valuation_cr: Decimal | None = Field(default=None, gt=0)
    pre_money_valuation_cr: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    source: str | None = Field(default=None, max_length=64)
    notes: str | None = None


class ValuationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    valuation_date: date
    post_money_valuation_cr: Decimal
    pre_money_valuation_cr: Decimal | None
    currency: str
    source: str | None
    notes: str | None
    created_by: int | None
    created_at: datetime


class MarkCurrentRequest(BaseModel):
    valuation_id: int
