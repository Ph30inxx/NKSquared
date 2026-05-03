"""Portfolio-level rollups: by sector, vintage, category, plus the headline
dashboard payload that the home page displays.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.mis import MisSubmission

_PENDING_STATUSES = ("Pending", "Submitted", "Under Review")


@dataclass
class Bucket:
    key: str
    invested_cr: Decimal
    current_cr: Decimal
    weighted_moic: Decimal | None
    count: int


def _bucket_company(
    buckets: dict[str, dict],
    key: str | None,
    *,
    invested: Decimal | None,
    current: Decimal | None,
) -> None:
    bucket = buckets.setdefault(
        key or "Unknown",
        {"invested_cr": Decimal(0), "current_cr": Decimal(0), "count": 0},
    )
    bucket["count"] += 1
    if invested is not None:
        bucket["invested_cr"] += abs(invested)
    if current is not None:
        bucket["current_cr"] += current


def _finalize(buckets: dict[str, dict]) -> list[Bucket]:
    out: list[Bucket] = []
    for key, b in buckets.items():
        moic = (
            b["current_cr"] / b["invested_cr"]
            if b["invested_cr"] not in (Decimal(0), 0)
            else None
        )
        out.append(
            Bucket(
                key=key,
                invested_cr=b["invested_cr"],
                current_cr=b["current_cr"],
                weighted_moic=moic,
                count=b["count"],
            )
        )
    out.sort(key=lambda x: x.invested_cr, reverse=True)
    return out


def _active_companies(db: Session) -> list[PortfolioCompany]:
    return list(
        db.execute(
            select(PortfolioCompany).where(PortfolioCompany.is_active.is_(True))
        ).scalars()
    )


def by_sector(db: Session) -> list[Bucket]:
    buckets: dict[str, dict] = {}
    for c in _active_companies(db):
        _bucket_company(
            buckets, c.sector, invested=c.investment_value_cr, current=c.current_value_cr
        )
    return _finalize(buckets)


def by_category(db: Session) -> list[Bucket]:
    buckets: dict[str, dict] = {}
    for c in _active_companies(db):
        _bucket_company(
            buckets,
            c.portfolio_type,
            invested=c.investment_value_cr,
            current=c.current_value_cr,
        )
    return _finalize(buckets)


def by_vintage(db: Session) -> list[Bucket]:
    buckets: dict[str, dict] = {}
    for c in _active_companies(db):
        key = (
            str(c.date_of_first_investment.year)
            if c.date_of_first_investment is not None
            else None
        )
        _bucket_company(
            buckets, key, invested=c.investment_value_cr, current=c.current_value_cr
        )
    out = _finalize(buckets)
    out.sort(key=lambda x: x.key)  # vintage years ascending
    return out


def summary(db: Session) -> dict:
    invested = Decimal(0)
    current = Decimal(0)
    count = 0
    for c in _active_companies(db):
        count += 1
        if c.investment_value_cr is not None:
            invested += abs(c.investment_value_cr)
        if c.current_value_cr is not None:
            current += c.current_value_cr
    weighted_moic = current / invested if invested != 0 else None
    pending = db.execute(
        select(func.count())
        .select_from(MisSubmission)
        .where(MisSubmission.status.in_(_PENDING_STATUSES))
    ).scalar_one()
    return {
        "total_invested_cr": invested,
        "current_value_cr": current,
        "weighted_moic": weighted_moic,
        "company_count": count,
        "pending_mis_count": pending,
    }


def dashboard_overview(db: Session) -> dict:
    return {
        "summary": summary(db),
        "by_sector": [b.__dict__ for b in by_sector(db)],
        "by_vintage": [b.__dict__ for b in by_vintage(db)],
        "by_category": [b.__dict__ for b in by_category(db)],
    }
