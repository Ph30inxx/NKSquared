from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.schemas.company import CompanyUpdate
from app.services import company_service


def _company_with_investment(db: Session, *, current: Decimal | None) -> PortfolioCompany:
    c = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        is_active=True,
        current_value_cr=current,
    )
    db.add(c)
    db.flush()
    db.add(
        PortfolioTransaction(
            company_id=c.id,
            transaction_date=date(2024, 1, 1),
            transaction_type="Investment",
            amount_cr=Decimal("-100"),
            original_currency="INR",
            original_amount=Decimal("100"),
            amount_inr_cr=Decimal("-100"),
        )
    )
    db.flush()
    return c


def test_patch_current_value_recomputes_moic(db: Session) -> None:
    c = _company_with_investment(db, current=Decimal("100"))
    company_service.update_company(
        db, c, CompanyUpdate(current_value_cr=Decimal("250")), user_id=None
    )
    db.refresh(c)
    # (250 + 0 realized) / 100 invested = 2.5
    assert c.moic == Decimal("2.5000")


def test_patch_unrelated_field_does_not_recompute(db: Session) -> None:
    c = _company_with_investment(db, current=Decimal("100"))
    # Stamp a stale moic so we can detect (lack of) recompute. Without changes
    # to current_value_cr, update_company must leave the persisted value alone.
    c.moic = Decimal("9.9999")
    db.flush()
    company_service.update_company(
        db, c, CompanyUpdate(notes="A note"), user_id=None
    )
    db.refresh(c)
    assert c.moic == Decimal("9.9999")
    assert c.notes == "A note"


def test_patch_no_op_does_not_recompute(db: Session) -> None:
    c = _company_with_investment(db, current=Decimal("100"))
    c.moic = Decimal("9.9999")
    db.flush()
    # Setting current_value_cr to its existing value is a no-op edit.
    company_service.update_company(
        db, c, CompanyUpdate(current_value_cr=Decimal("100")), user_id=None
    )
    db.refresh(c)
    assert c.moic == Decimal("9.9999")
