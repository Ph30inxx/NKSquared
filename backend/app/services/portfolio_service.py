"""Portfolio-level rollups: by sector, vintage, category, plus the headline
dashboard payload that the home page displays.

Sprint 8 perf pass: `summary`, `by_sector`, and `by_category` now read from
the `portfolio_aggregates_mv` materialized view (defined in the initial
migration, refreshed every 5 minutes by `app.tasks.aggregates`). `by_vintage`
remains a Python rollup since vintage isn't materialized.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select, text
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


def _read_mv_buckets(db: Session, scope_type: str) -> list[Bucket] | None:
    """Read the matching scope from `portfolio_aggregates_mv`. Returns None if
    not on Postgres (SQLite tests) so callers can fall back to the Python
    rollup without dirtying the active session."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return None
    rows = db.execute(
        text(
            """
            SELECT scope_value, total_invested_cr, current_value_cr, moic, company_count
            FROM portfolio_aggregates_mv
            WHERE scope_type = :scope_type
            """
        ),
        {"scope_type": scope_type},
    ).all()

    out = [
        Bucket(
            key=r.scope_value or "Unknown",
            invested_cr=Decimal(r.total_invested_cr) if r.total_invested_cr is not None else Decimal(0),
            current_cr=Decimal(r.current_value_cr) if r.current_value_cr is not None else Decimal(0),
            weighted_moic=Decimal(r.moic) if r.moic is not None else None,
            count=int(r.company_count or 0),
        )
        for r in rows
    ]
    out.sort(key=lambda x: x.invested_cr, reverse=True)
    return out


def by_sector(db: Session) -> list[Bucket]:
    cached = _read_mv_buckets(db, "SECTOR")
    if cached is not None:
        return cached
    buckets: dict[str, dict] = {}
    for c in _active_companies(db):
        _bucket_company(
            buckets, c.sector, invested=c.investment_value_cr, current=c.current_value_cr
        )
    return _finalize(buckets)


def by_category(db: Session) -> list[Bucket]:
    cached = _read_mv_buckets(db, "PORTFOLIO_TYPE")
    if cached is not None:
        return cached
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
    pending = db.execute(
        select(func.count())
        .select_from(MisSubmission)
        .where(MisSubmission.status.in_(_PENDING_STATUSES))
    ).scalar_one()

    row = None
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        row = db.execute(
            text(
                """
                SELECT total_invested_cr, current_value_cr, moic, company_count
                FROM portfolio_aggregates_mv
                WHERE scope_type = 'TOTAL'
                """
            )
        ).first()

    if row is not None:
        return {
            "total_invested_cr": Decimal(row.total_invested_cr or 0),
            "current_value_cr": Decimal(row.current_value_cr or 0),
            "weighted_moic": Decimal(row.moic) if row.moic is not None else None,
            "company_count": int(row.company_count or 0),
            "pending_mis_count": pending,
        }

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
