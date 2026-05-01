from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.schemas.transaction import TransactionCreate
from app.services import fx_service, transaction_service


def _company(db: Session) -> PortfolioCompany:
    c = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c


def test_non_inr_with_seeded_rate_auto_populates_inr(db: Session) -> None:
    c = _company(db)
    fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 1, 1),
        rate=Decimal("83.00"),
        source="seed",
    )
    db.commit()
    txn = transaction_service.create_transaction(
        db,
        company_id=c.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 1, 15),  # within 30-day window of seed date
            transaction_type="Investment",
            amount=Decimal("10"),
            currency="USD",
        ),
        user_id=None,
    )
    assert txn.fx_rate_used == Decimal("83.00")
    # 10 USD × 83 = 830, signed negative for Investment
    assert txn.amount_inr_cr == Decimal("-830.00")


def test_non_inr_without_rate_then_recompute_after_seed(db: Session) -> None:
    c = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=c.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 4, 1),
            transaction_type="Investment",
            amount=Decimal("5"),
            currency="AUD",
        ),
        user_id=None,
    )
    assert txn.amount_inr_cr is None
    assert txn.fx_rate_used is None

    # Operator now seeds the AUD rate and triggers recompute.
    fx_service.upsert_fx_rate(
        db,
        from_currency="AUD",
        to_currency="INR",
        on_date=date(2024, 4, 1),
        rate=Decimal("55.00"),
    )
    db.commit()

    updated, still = transaction_service.recompute_company_fx(db, company_id=c.id)
    db.commit()
    assert updated == 1
    assert still == 0

    db.refresh(txn)
    assert txn.fx_rate_used == Decimal("55.00")
    assert txn.amount_inr_cr == Decimal("-275.00")  # -(5 × 55)


def test_explicit_fx_overrides_lookup(db: Session) -> None:
    c = _company(db)
    fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 1, 1),
        rate=Decimal("83.00"),
    )
    db.commit()
    txn = transaction_service.create_transaction(
        db,
        company_id=c.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 1, 15),
            transaction_type="Investment",
            amount=Decimal("10"),
            currency="USD",
            fx_rate_used=Decimal("85.00"),  # caller-supplied rate wins
        ),
        user_id=None,
    )
    assert txn.fx_rate_used == Decimal("85.00")
    assert txn.amount_inr_cr == Decimal("-850.00")
