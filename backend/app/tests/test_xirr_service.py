from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.services.xirr_service import compute_company_xirr


def _company(db: Session, *, current: Decimal | None = None) -> PortfolioCompany:
    c = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        current_value_cr=current,
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c


def _add(db: Session, c: PortfolioCompany, *, txn_type: str, amt_inr: Decimal, on: date) -> None:
    db.add(
        PortfolioTransaction(
            company_id=c.id,
            transaction_date=on,
            transaction_type=txn_type,
            amount_cr=amt_inr,
            original_currency="INR",
            original_amount=abs(amt_inr),
            amount_inr_cr=amt_inr,
        )
    )
    db.flush()


def test_investment_then_2x_exit_one_year_later_yields_100_percent(db: Session) -> None:
    c = _company(db)
    _add(db, c, txn_type="Investment", amt_inr=Decimal("-100"), on=date(2024, 1, 1))
    _add(db, c, txn_type="Full_exit", amt_inr=Decimal("200"), on=date(2025, 1, 1))
    irr = compute_company_xirr(db, c.id)
    assert irr is not None
    # XIRR uses 365-day year basis. (2025-01-01 - 2024-01-01) is 366 days in this leap span,
    # so the annualised rate is just under 100% — allow a wide band either way.
    assert Decimal("0.99") <= irr <= Decimal("1.01")


def test_investment_with_matching_current_value_one_year_later_yields_zero(db: Session) -> None:
    c = _company(db, current=Decimal("100"))
    one_year_ago = date.today() - timedelta(days=365)
    _add(db, c, txn_type="Investment", amt_inr=Decimal("-100"), on=one_year_ago)
    irr = compute_company_xirr(db, c.id)
    assert irr is not None
    assert abs(irr) < Decimal("0.01")


def test_fewer_than_two_cashflows_returns_none(db: Session) -> None:
    c = _company(db)
    _add(db, c, txn_type="Investment", amt_inr=Decimal("-100"), on=date(2024, 1, 1))
    # No exit, no current value → only one cash flow → IRR undefined.
    assert compute_company_xirr(db, c.id) is None


def test_same_day_only_returns_none(db: Session) -> None:
    c = _company(db)
    _add(db, c, txn_type="Investment", amt_inr=Decimal("-100"), on=date(2024, 1, 1))
    _add(db, c, txn_type="Distribution", amt_inr=Decimal("100"), on=date(2024, 1, 1))
    assert compute_company_xirr(db, c.id) is None


def test_skips_rows_without_amount_inr_cr(db: Session) -> None:
    c = _company(db, current=Decimal("100"))
    one_year_ago = date.today() - timedelta(days=365)
    _add(db, c, txn_type="Investment", amt_inr=Decimal("-100"), on=one_year_ago)
    # Non-INR row with no fx → amount_inr_cr null → must not blow up XIRR.
    db.add(
        PortfolioTransaction(
            company_id=c.id,
            transaction_date=date.today(),
            transaction_type="Follow_on",
            amount_cr=Decimal("-50"),
            original_currency="USD",
            original_amount=Decimal("50"),
            amount_inr_cr=None,
        )
    )
    db.flush()
    irr = compute_company_xirr(db, c.id)
    assert irr is not None
    assert abs(irr) < Decimal("0.01")
