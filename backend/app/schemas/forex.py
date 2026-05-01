from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ForexRateCreate(BaseModel):
    from_currency: str = Field(min_length=3, max_length=10)
    to_currency: str = Field(default="INR", min_length=3, max_length=10)
    rate: Decimal = Field(gt=0)
    effective_date: date
    source: str | None = Field(default=None, max_length=64)

    @field_validator("from_currency", "to_currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class ForexRateBulkCreate(BaseModel):
    rates: list[ForexRateCreate]


class ForexRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_date: date
    source: str | None
    created_at: datetime
