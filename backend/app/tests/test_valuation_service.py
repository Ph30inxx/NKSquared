from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.models.valuation import Valuation
from app.services import valuation_service
from app.schemas.valuation import ValuationCreate


def _company_with_shareholding(db: Session, pct: Decimal | None) -> PortfolioCompany:
    c = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        is_active=True,
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
            shareholding_pct=pct,
        )
    )
    db.flush()
    return c


def test_mark_current_uses_pro_rata(db: Session) -> None:
    c = _company_with_shareholding(db, Decimal("0.25"))
    v = valuation_service.create_valuation(
        db,
        company_id=c.id,
        payload=ValuationCreate(
            valuation_date=date(2025, 6, 1),
            post_money_valuation_cr=Decimal("400"),
            source="Internal",
        ),
        user_id=None,
    )
    valuation_service.mark_current(db, c, v, user_id=None)
    db.refresh(c)
    # 400 × 0.25 = 100
    assert c.current_value_cr == Decimal("100.0000")


def test_mark_current_without_shareholding_raises(db: Session) -> None:
    c = _company_with_shareholding(db, None)
    v = valuation_service.create_valuation(
        db,
        company_id=c.id,
        payload=ValuationCreate(
            valuation_date=date(2025, 6, 1),
            post_money_valuation_cr=Decimal("400"),
        ),
        user_id=None,
    )
    with pytest.raises(ValueError, match="shareholding"):
        valuation_service.mark_current(db, c, v, user_id=None)


def test_mark_current_picks_latest_shareholding(db: Session) -> None:
    c = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        is_active=True,
    )
    db.add(c)
    db.flush()
    # Earlier 50% holding…
    db.add(
        PortfolioTransaction(
            company_id=c.id,
            transaction_date=date(2023, 1, 1),
            transaction_type="Investment",
            amount_cr=Decimal("-100"),
            original_currency="INR",
            original_amount=Decimal("100"),
            amount_inr_cr=Decimal("-100"),
            shareholding_pct=Decimal("0.50"),
        )
    )
    # …diluted to 30% in a later round.
    db.add(
        PortfolioTransaction(
            company_id=c.id,
            transaction_date=date(2024, 6, 1),
            transaction_type="Follow_on",
            amount_cr=Decimal("-50"),
            original_currency="INR",
            original_amount=Decimal("50"),
            amount_inr_cr=Decimal("-50"),
            shareholding_pct=Decimal("0.30"),
        )
    )
    db.flush()
    v = valuation_service.create_valuation(
        db,
        company_id=c.id,
        payload=ValuationCreate(
            valuation_date=date(2025, 6, 1),
            post_money_valuation_cr=Decimal("1000"),
        ),
        user_id=None,
    )
    valuation_service.mark_current(db, c, v, user_id=None)
    db.refresh(c)
    # 1000 × 0.30 = 300 (uses the *latest* shareholding, not the original)
    assert c.current_value_cr == Decimal("300.0000")
