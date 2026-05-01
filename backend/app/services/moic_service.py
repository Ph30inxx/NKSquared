from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.schemas.transaction import NEGATIVE_TYPES, POSITIVE_TYPES


@dataclass
class MoicResult:
    invested: Decimal  # absolute INR Cr put in (always >= 0)
    realized: Decimal  # INR Cr returned (always >= 0)
    current: Decimal   # current_value_cr from the company row
    moic: Decimal | None


def _zero() -> Decimal:
    return Decimal("0")


def compute_company_moic(db: Session, company_id: int) -> MoicResult:
    """
    Per § 4.4:
        MOIC = (current_value + realized_proceeds) / total_invested

    - total_invested  = ABS sum of amount_inr_cr where transaction_type ∈ {Investment, Follow_on}
    - realized        = sum of amount_inr_cr where transaction_type ∈ {Partial_exit, Full_exit, Distribution}
    - current_value   = portfolio_companies.current_value_cr (set manually until Sprint 3 valuations)

    Transactions whose `amount_inr_cr` is NULL (non-INR with no FX rate yet) are skipped.
    Returns moic=None when there's no invested capital (instead of dividing by zero).
    """
    company = db.get(PortfolioCompany, company_id)
    if company is None:
        raise ValueError(f"Company {company_id} not found")

    rows = db.execute(
        select(PortfolioTransaction.transaction_type, PortfolioTransaction.amount_inr_cr).where(
            PortfolioTransaction.company_id == company_id
        )
    ).all()

    invested = _zero()
    realized = _zero()
    for txn_type, amount in rows:
        if amount is None:
            continue
        if txn_type in NEGATIVE_TYPES:
            invested += abs(amount)
        elif txn_type in POSITIVE_TYPES:
            realized += amount
        # ZERO_TYPES (Write_down, Write_off) contribute nothing to the cash-flow ratio.

    current = company.current_value_cr or _zero()
    moic = (current + realized) / invested if invested > 0 else None
    return MoicResult(invested=invested, realized=realized, current=current, moic=moic)


def recompute_company_moic(db: Session, company_id: int) -> MoicResult:
    """Compute MOIC and persist it on the company row (caller commits)."""
    result = compute_company_moic(db, company_id)
    company = db.get(PortfolioCompany, company_id)
    assert company is not None  # compute_company_moic already raised if missing
    company.moic = result.moic
    company.investment_value_cr = -result.invested if result.invested > 0 else _zero()
    db.flush()
    return result
