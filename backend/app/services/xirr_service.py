from datetime import date
from decimal import Decimal

import pyxirr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction


def compute_company_xirr(db: Session, company_id: int) -> Decimal | None:
    """
    Per § 4.4: cash flows are the company's transactions (signed amount_inr_cr,
    negative for outflows) plus a synthetic positive flow at today equal to
    `current_value_cr`. Returns annualised IRR as a Decimal, or None if
    underdetermined (<2 cashflows, all on the same day, or solver fails).
    """
    company = db.get(PortfolioCompany, company_id)
    if company is None:
        return None

    rows = db.execute(
        select(PortfolioTransaction.transaction_date, PortfolioTransaction.amount_inr_cr).where(
            PortfolioTransaction.company_id == company_id,
            PortfolioTransaction.amount_inr_cr.is_not(None),
        )
    ).all()

    dates: list[date] = []
    amounts: list[float] = []
    for txn_date, amount in rows:
        if amount == 0:
            continue
        dates.append(txn_date)
        amounts.append(float(amount))

    today = date.today()
    if company.current_value_cr is not None and company.current_value_cr > 0:
        dates.append(today)
        amounts.append(float(company.current_value_cr))

    if len(dates) < 2 or len(set(dates)) < 2:
        return None
    # XIRR needs at least one positive and one negative cash flow.
    if not any(a < 0 for a in amounts) or not any(a > 0 for a in amounts):
        return None

    try:
        irr = pyxirr.xirr(dates, amounts)
    except Exception:
        return None
    if irr is None:
        return None
    return Decimal(str(irr))


def recompute_company_xirr(db: Session, company_id: int) -> Decimal | None:
    """Compute XIRR and persist it to companies.irr (caller commits)."""
    irr = compute_company_xirr(db, company_id)
    company = db.get(PortfolioCompany, company_id)
    if company is None:
        return None
    company.irr = irr
    db.flush()
    return irr
