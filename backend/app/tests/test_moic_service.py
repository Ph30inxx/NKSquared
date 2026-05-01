from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.services.moic_service import compute_company_moic, recompute_company_moic


def _make_company(db: Session, *, current_value: Decimal | None = None) -> PortfolioCompany:
    company = PortfolioCompany(
        company_name="Acme",
        currency="INR",
        reporting_frequency="Monthly",
        current_value_cr=current_value,
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


def _add_txn(
    db: Session,
    company: PortfolioCompany,
    *,
    txn_type: str,
    magnitude: Decimal,
    inr_magnitude: Decimal | None = None,
    txn_date: date = date(2024, 1, 1),
) -> None:
    """`magnitude` is positive; we sign amount_cr/amount_inr_cr per § 3.2."""
    if inr_magnitude is None:
        inr_magnitude = magnitude
    if txn_type in ("Investment", "Follow_on"):
        amount_cr = -magnitude
        amount_inr = -inr_magnitude if inr_magnitude is not None else None
    elif txn_type in ("Partial_exit", "Full_exit", "Distribution"):
        amount_cr = magnitude
        amount_inr = inr_magnitude
    else:
        amount_cr = Decimal("0")
        amount_inr = Decimal("0")
    db.add(
        PortfolioTransaction(
            company_id=company.id,
            transaction_date=txn_date,
            transaction_type=txn_type,
            amount_cr=amount_cr,
            original_currency="INR",
            original_amount=magnitude,
            amount_inr_cr=amount_inr,
        )
    )
    db.flush()


def test_moic_single_investment_with_current_value(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("150"))
    _add_txn(db, company, txn_type="Investment", magnitude=Decimal("100"))

    result = compute_company_moic(db, company.id)

    assert result.invested == Decimal("100")
    assert result.realized == Decimal("0")
    assert result.current == Decimal("150")
    assert result.moic == Decimal("1.5")


def test_moic_with_partial_exit(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("120"))
    _add_txn(db, company, txn_type="Investment", magnitude=Decimal("100"))
    _add_txn(db, company, txn_type="Partial_exit", magnitude=Decimal("30"))

    result = compute_company_moic(db, company.id)

    assert result.invested == Decimal("100")
    assert result.realized == Decimal("30")
    assert result.current == Decimal("120")
    assert result.moic == Decimal("1.5")  # (120 + 30) / 100


def test_moic_with_followons_and_distribution(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("180"))
    _add_txn(db, company, txn_type="Investment", magnitude=Decimal("100"))
    _add_txn(db, company, txn_type="Follow_on", magnitude=Decimal("50"))
    _add_txn(db, company, txn_type="Distribution", magnitude=Decimal("20"))

    result = compute_company_moic(db, company.id)

    assert result.invested == Decimal("150")
    assert result.realized == Decimal("20")
    # (180 + 20) / 150 = 1.3333...
    assert result.moic is not None
    assert round(result.moic, 6) == Decimal("1.333333")


def test_moic_zero_invested_returns_none(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("100"))
    # Distribution-only is unusual but must not divide by zero.
    _add_txn(db, company, txn_type="Distribution", magnitude=Decimal("5"))

    result = compute_company_moic(db, company.id)

    assert result.invested == Decimal("0")
    assert result.moic is None


def test_moic_skips_rows_without_amount_inr_cr(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("120"))
    _add_txn(db, company, txn_type="Investment", magnitude=Decimal("100"))
    # Non-INR row that hasn't been FX-converted yet (Sprint 3 will fix these).
    db.add(
        PortfolioTransaction(
            company_id=company.id,
            transaction_date=date(2024, 2, 1),
            transaction_type="Follow_on",
            amount_cr=Decimal("-50"),
            original_currency="USD",
            original_amount=Decimal("50"),
            amount_inr_cr=None,
            fx_rate_used=None,
        )
    )
    db.flush()

    result = compute_company_moic(db, company.id)

    # Only the INR row is counted.
    assert result.invested == Decimal("100")
    assert result.moic == Decimal("1.2")


def test_moic_writeoff_does_not_count(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("0"))
    _add_txn(db, company, txn_type="Investment", magnitude=Decimal("100"))
    _add_txn(db, company, txn_type="Write_off", magnitude=Decimal("0"))

    result = compute_company_moic(db, company.id)

    assert result.invested == Decimal("100")
    assert result.realized == Decimal("0")
    # Total return = 0 → MOIC = 0
    assert result.moic == Decimal("0")


def test_recompute_persists_to_company_row(db: Session) -> None:
    company = _make_company(db, current_value=Decimal("150"))
    _add_txn(db, company, txn_type="Investment", magnitude=Decimal("100"))

    recompute_company_moic(db, company.id)

    refreshed = db.get(PortfolioCompany, company.id)
    assert refreshed is not None
    assert refreshed.moic == Decimal("1.5")
    # investment_value_cr is the negative-signed total invested (§ 3.2 convention).
    assert refreshed.investment_value_cr == Decimal("-100")
