from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TransactionType = Literal[
    "Investment",
    "Follow_on",
    "Partial_exit",
    "Full_exit",
    "Distribution",
    "Write_down",
    "Write_off",
]

# § 3.2 sign convention. Backend uses these to sign amount_cr from the user-supplied magnitude.
NEGATIVE_TYPES: frozenset[str] = frozenset({"Investment", "Follow_on"})
POSITIVE_TYPES: frozenset[str] = frozenset({"Partial_exit", "Full_exit", "Distribution"})
ZERO_TYPES: frozenset[str] = frozenset({"Write_down", "Write_off"})


class TransactionCreate(BaseModel):
    transaction_date: date
    transaction_type: TransactionType

    # Always positive — the backend signs amount_cr based on transaction_type.
    # Write_down / Write_off should pass 0 (or omit and we default to 0).
    amount: Decimal = Field(ge=0)
    currency: str = Field(default="INR", min_length=3, max_length=10)
    fx_rate_used: Decimal | None = Field(default=None, gt=0)

    series: str | None = Field(default=None, max_length=64)
    instrument_type: str | None = Field(default=None, max_length=64)
    investing_entity: str | None = Field(default=None, max_length=128)
    shares: Decimal | None = Field(default=None, ge=0)
    share_price: Decimal | None = Field(default=None, ge=0)
    pre_money_valuation_cr: Decimal | None = Field(default=None, ge=0)
    post_money_valuation_cr: Decimal | None = Field(default=None, ge=0)
    shareholding_pct: Decimal | None = Field(default=None, ge=0, le=1)
    ssa_reference: str | None = Field(default=None, max_length=255)
    ssa_recorded_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("transaction_date")
    @classmethod
    def _no_future_dates(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("Transaction date cannot be in the future")
        return v

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str) -> str:
        return v.upper()


class TransactionUpdate(BaseModel):
    transaction_date: date | None = None
    transaction_type: TransactionType | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    fx_rate_used: Decimal | None = Field(default=None, gt=0)
    series: str | None = Field(default=None, max_length=64)
    instrument_type: str | None = Field(default=None, max_length=64)
    investing_entity: str | None = Field(default=None, max_length=128)
    shares: Decimal | None = Field(default=None, ge=0)
    share_price: Decimal | None = Field(default=None, ge=0)
    pre_money_valuation_cr: Decimal | None = Field(default=None, ge=0)
    post_money_valuation_cr: Decimal | None = Field(default=None, ge=0)
    shareholding_pct: Decimal | None = Field(default=None, ge=0, le=1)
    ssa_reference: str | None = Field(default=None, max_length=255)
    ssa_recorded_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("transaction_date")
    @classmethod
    def _no_future_dates(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Transaction date cannot be in the future")
        return v

    @field_validator("currency")
    @classmethod
    def _upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    transaction_date: date
    transaction_type: str
    amount_cr: Decimal
    original_currency: str
    original_amount: Decimal | None
    amount_inr_cr: Decimal | None
    fx_rate_used: Decimal | None
    series: str | None
    instrument_type: str | None
    investing_entity: str | None
    shares: Decimal | None
    share_price: Decimal | None
    pre_money_valuation_cr: Decimal | None
    post_money_valuation_cr: Decimal | None
    shareholding_pct: Decimal | None
    ssa_reference: str | None
    ssa_recorded_amount: Decimal | None
    notes: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
