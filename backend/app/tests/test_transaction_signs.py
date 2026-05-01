from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.services import transaction_service


def _company(db: Session) -> PortfolioCompany:
    company = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


def test_investment_amount_is_negated(db: Session) -> None:
    company = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=company.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 1, 1),
            transaction_type="Investment",
            amount=Decimal("100"),
            currency="INR",
        ),
        user_id=None,
    )
    assert txn.amount_cr == Decimal("-100")
    assert txn.amount_inr_cr == Decimal("-100")
    assert txn.original_amount == Decimal("100")
    assert txn.fx_rate_used == Decimal("1")


def test_partial_exit_amount_is_positive(db: Session) -> None:
    company = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=company.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 6, 1),
            transaction_type="Partial_exit",
            amount=Decimal("40"),
            currency="INR",
        ),
        user_id=None,
    )
    assert txn.amount_cr == Decimal("40")
    assert txn.amount_inr_cr == Decimal("40")


def test_write_off_amount_is_zero(db: Session) -> None:
    company = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=company.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 6, 1),
            transaction_type="Write_off",
            amount=Decimal("0"),
            currency="INR",
        ),
        user_id=None,
    )
    assert txn.amount_cr == Decimal("0")
    assert txn.amount_inr_cr == Decimal("0")


def test_non_inr_without_fx_leaves_inr_amount_null(db: Session) -> None:
    company = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=company.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 1, 1),
            transaction_type="Investment",
            amount=Decimal("50"),
            currency="USD",
        ),
        user_id=None,
    )
    assert txn.amount_cr == Decimal("-50")  # original-currency signed magnitude
    assert txn.amount_inr_cr is None
    assert txn.fx_rate_used is None
    assert txn.original_currency == "USD"


def test_non_inr_with_fx_converts(db: Session) -> None:
    company = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=company.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 1, 1),
            transaction_type="Investment",
            amount=Decimal("50"),
            currency="USD",
            fx_rate_used=Decimal("83.5"),
        ),
        user_id=None,
    )
    assert txn.amount_inr_cr == Decimal("-4175.0")  # -(50 * 83.5)
    assert txn.fx_rate_used == Decimal("83.5")


def test_future_date_rejected_at_schema_layer() -> None:
    with pytest.raises(ValueError, match="future"):
        TransactionCreate(
            transaction_date=date(2999, 1, 1),
            transaction_type="Investment",
            amount=Decimal("10"),
        )


def test_update_changing_type_re_signs_amount(db: Session) -> None:
    company = _company(db)
    txn = transaction_service.create_transaction(
        db,
        company_id=company.id,
        payload=TransactionCreate(
            transaction_date=date(2024, 1, 1),
            transaction_type="Investment",
            amount=Decimal("100"),
            currency="INR",
        ),
        user_id=None,
    )
    updated = transaction_service.update_transaction(
        db,
        txn,
        TransactionUpdate(transaction_type="Partial_exit"),
        user_id=None,
    )
    assert updated.amount_cr == Decimal("100")
    assert updated.amount_inr_cr == Decimal("100")
