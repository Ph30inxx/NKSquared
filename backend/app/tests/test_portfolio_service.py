from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.mis import MisSubmission
from app.services import portfolio_service


def _co(**kwargs) -> PortfolioCompany:
    defaults = dict(
        company_name="X",
        sector="Food",
        portfolio_type="Entity_D_Core",
        date_of_first_investment=date(2022, 4, 1),
        investment_value_cr=Decimal("-10"),
        current_value_cr=Decimal("18"),
        is_active=True,
    )
    defaults.update(kwargs)
    return PortfolioCompany(**defaults)


def test_summary_aggregates_invested_with_abs(db: Session) -> None:
    db.add_all([
        _co(company_name="A", investment_value_cr=Decimal("-10"), current_value_cr=Decimal("12")),
        _co(company_name="B", investment_value_cr=Decimal("-5"), current_value_cr=Decimal("8")),
    ])
    db.flush()
    s = portfolio_service.summary(db)
    assert s["total_invested_cr"] == Decimal("15")
    assert s["current_value_cr"] == Decimal("20")
    assert s["weighted_moic"] == Decimal("20") / Decimal("15")
    assert s["company_count"] == 2


def test_by_sector_groups_and_sorts(db: Session) -> None:
    db.add_all([
        _co(company_name="A", sector="Food", investment_value_cr=Decimal("-10"), current_value_cr=Decimal("12")),
        _co(company_name="B", sector="Food", investment_value_cr=Decimal("-5"), current_value_cr=Decimal("4")),
        _co(company_name="C", sector="Tech", investment_value_cr=Decimal("-20"), current_value_cr=Decimal("30")),
    ])
    db.flush()
    out = portfolio_service.by_sector(db)
    keys = [b.key for b in out]
    assert keys == ["Tech", "Food"]
    food = next(b for b in out if b.key == "Food")
    assert food.invested_cr == Decimal("15")
    assert food.count == 2


def test_by_vintage_groups_by_year(db: Session) -> None:
    db.add_all([
        _co(company_name="A", date_of_first_investment=date(2021, 5, 1)),
        _co(company_name="B", date_of_first_investment=date(2021, 9, 1)),
        _co(company_name="C", date_of_first_investment=date(2023, 1, 1)),
    ])
    db.flush()
    out = portfolio_service.by_vintage(db)
    assert [b.key for b in out] == ["2021", "2023"]
    assert out[0].count == 2


def test_summary_pending_mis_count(db: Session) -> None:
    db.add(_co(company_name="A"))
    db.add_all([
        MisSubmission(company_id="company_a", period_year=2026, period_month=1, fiscal_year="FY26", status="Pending"),
        MisSubmission(company_id="company_a", period_year=2026, period_month=2, fiscal_year="FY26", status="Submitted"),
        MisSubmission(company_id="company_a", period_year=2026, period_month=3, fiscal_year="FY26", status="Approved"),
    ])
    db.flush()
    s = portfolio_service.summary(db)
    assert s["pending_mis_count"] == 2
