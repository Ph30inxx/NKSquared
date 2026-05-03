"""Time-series and per-company summary builders driven by the mis_monthly /
mis_bu_monthly tables. Powers the company detail page charts and the MIS
summary endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models.mis import MisAnomaly, MisBuMonthly, MisMonthly, MisSubmission

# Metrics the timeseries endpoint exposes by default.
DEFAULT_METRICS = (
    "revenue_lacs",
    "cogs_lacs",
    "gross_margin_lacs",
    "ebitda_lacs",
    "gross_margin_pct",
)

# Metrics summed across geographies (vs. averaged).
SUMMED_METRICS = {
    "revenue_lacs",
    "cogs_lacs",
    "gross_margin_lacs",
    "ebitda_lacs",
    "indirect_income_lacs",
    "total_income_lacs",
    "total_operating_costs_lacs",
    "manpower_cost_lacs",
    "rent_lacs",
    "utilities_lacs",
    "marketing_lacs",
    "admin_lacs",
}

CHANNEL_FIELDS = (
    "channel_dine_in_lacs",
    "channel_aggregator_a_lacs",
    "channel_aggregator_b_lacs",
    "channel_aggregator_d_lacs",
    "channel_catering_lacs",
    "channel_franchise_lacs",
)


@dataclass
class TimeseriesPoint:
    month: date
    value: Decimal | None
    mom_pct: Decimal | None


def _months_window(latest: date, *, window: int = 24) -> list[date]:
    """Return `window` first-of-month dates ending at `latest`, oldest first."""
    out: list[date] = []
    y, m = latest.year, latest.month
    for _ in range(window):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _consolidated_value(
    rows: Iterable[MisMonthly], metric: str
) -> Decimal | None:
    """Aggregate per-geography rows into one value for a single month."""
    values = [getattr(r, metric) for r in rows if getattr(r, metric) is not None]
    if not values:
        return None
    if metric in SUMMED_METRICS:
        return sum(values, Decimal(0))
    # Default = simple average (used for percentage metrics).
    return sum(values, Decimal(0)) / Decimal(len(values))


def _mom_pct(curr: Decimal | None, prev: Decimal | None) -> Decimal | None:
    if curr is None or prev is None or prev == 0:
        return None
    return (curr - prev) / abs(prev) * Decimal(100)


def _latest_month(db: Session, company_code: str) -> date | None:
    return db.execute(
        select(MisMonthly.month_date)
        .where(MisMonthly.company_id == company_code)
        .order_by(MisMonthly.month_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_timeseries(
    db: Session,
    company_code: str,
    *,
    metrics: list[str] | None = None,
    from_month: date | None = None,
    to_month: date | None = None,
    breakdown: str = "none",
) -> dict:
    """Return time-series of `metrics` for the company.

    breakdown:
      - "none"       — consolidated values across all geographies.
      - "geography"  — series per geography.
      - "channels"   — BU-level channel mix from mis_bu_monthly.
    """
    metrics = list(metrics) if metrics else list(DEFAULT_METRICS)
    if breakdown == "channels":
        return _channels_timeseries(db, company_code, from_month, to_month)

    latest = to_month or _latest_month(db, company_code)
    if latest is None:
        return {"company_code": company_code, "months": [], "series": {}}
    months = _months_window(latest, window=24)
    if from_month is not None:
        months = [m for m in months if m >= from_month]
    if not months:
        return {"company_code": company_code, "months": [], "series": {}}

    rows = db.execute(
        select(MisMonthly).where(
            and_(
                MisMonthly.company_id == company_code,
                MisMonthly.month_date >= months[0],
                MisMonthly.month_date <= months[-1],
            )
        )
    ).scalars().all()

    if breakdown == "geography":
        return _geography_timeseries(rows, months, metrics, company_code)

    by_month: dict[date, list[MisMonthly]] = {}
    for r in rows:
        if r.month_date is not None:
            by_month.setdefault(r.month_date, []).append(r)

    series: dict[str, list[TimeseriesPoint]] = {}
    for metric in metrics:
        points: list[TimeseriesPoint] = []
        prev: Decimal | None = None
        for m in months:
            curr = _consolidated_value(by_month.get(m, []), metric)
            points.append(TimeseriesPoint(month=m, value=curr, mom_pct=_mom_pct(curr, prev)))
            prev = curr
        series[metric] = points

    return {
        "company_code": company_code,
        "months": months,
        "series": {k: [p.__dict__ for p in v] for k, v in series.items()},
    }


def _geography_timeseries(
    rows: list[MisMonthly], months: list[date], metrics: list[str], company_code: str
) -> dict:
    geos = sorted({r.geography for r in rows if r.geography})
    by_month_geo: dict[tuple[date, str], MisMonthly] = {}
    for r in rows:
        if r.month_date is not None and r.geography is not None:
            by_month_geo[(r.month_date, r.geography)] = r

    series: dict[str, dict[str, list[TimeseriesPoint]]] = {}
    for metric in metrics:
        per_geo: dict[str, list[TimeseriesPoint]] = {}
        for geo in geos:
            points: list[TimeseriesPoint] = []
            prev: Decimal | None = None
            for m in months:
                row = by_month_geo.get((m, geo))
                curr = getattr(row, metric, None) if row is not None else None
                points.append(
                    TimeseriesPoint(month=m, value=curr, mom_pct=_mom_pct(curr, prev))
                )
                prev = curr
            per_geo[geo] = points
        series[metric] = per_geo

    return {
        "company_code": company_code,
        "months": months,
        "series": {
            k: {g: [p.__dict__ for p in pts] for g, pts in v.items()}
            for k, v in series.items()
        },
    }


def _channels_timeseries(
    db: Session,
    company_code: str,
    from_month: date | None,
    to_month: date | None,
) -> dict:
    latest = to_month or db.execute(
        select(MisBuMonthly.month_date)
        .where(MisBuMonthly.company_id == company_code)
        .order_by(MisBuMonthly.month_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest is None:
        return {"company_code": company_code, "months": [], "series": {}}

    months = _months_window(latest, window=24)
    if from_month is not None:
        months = [m for m in months if m >= from_month]

    rows = db.execute(
        select(MisBuMonthly).where(
            and_(
                MisBuMonthly.company_id == company_code,
                MisBuMonthly.month_date >= months[0],
                MisBuMonthly.month_date <= months[-1],
            )
        )
    ).scalars().all()

    by_month: dict[date, list[MisBuMonthly]] = {}
    for r in rows:
        if r.month_date is not None:
            by_month.setdefault(r.month_date, []).append(r)

    series: dict[str, list[TimeseriesPoint]] = {}
    for ch in CHANNEL_FIELDS:
        points: list[TimeseriesPoint] = []
        prev: Decimal | None = None
        for m in months:
            vs = [
                getattr(r, ch) for r in by_month.get(m, []) if getattr(r, ch) is not None
            ]
            curr = sum(vs, Decimal(0)) if vs else None
            points.append(TimeseriesPoint(month=m, value=curr, mom_pct=_mom_pct(curr, prev)))
            prev = curr
        series[ch] = points

    return {
        "company_code": company_code,
        "months": months,
        "series": {k: [p.__dict__ for p in v] for k, v in series.items()},
    }


def get_summary(db: Session, company_code: str) -> dict | None:
    """Latest-period KPIs + waterfall components + BU breakdown + active anomaly count."""
    latest = _latest_month(db, company_code)
    if latest is None:
        return None
    prev = date(latest.year - (1 if latest.month == 1 else 0), (latest.month - 1) or 12, 1)

    monthly_curr = db.execute(
        select(MisMonthly).where(
            and_(MisMonthly.company_id == company_code, MisMonthly.month_date == latest)
        )
    ).scalars().all()
    monthly_prev = db.execute(
        select(MisMonthly).where(
            and_(MisMonthly.company_id == company_code, MisMonthly.month_date == prev)
        )
    ).scalars().all()

    summary_metrics = ("revenue_lacs", "cogs_lacs", "gross_margin_lacs", "ebitda_lacs")
    kpis: dict[str, dict] = {}
    for metric in summary_metrics:
        curr = _consolidated_value(monthly_curr, metric)
        prv = _consolidated_value(monthly_prev, metric)
        kpis[metric] = {
            "value": curr,
            "prev_value": prv,
            "mom_pct": _mom_pct(curr, prv),
        }

    revenue = kpis["revenue_lacs"]["value"]
    cogs = kpis["cogs_lacs"]["value"]
    gp = kpis["gross_margin_lacs"]["value"]
    ebitda = kpis["ebitda_lacs"]["value"]
    opex = (
        gp - ebitda if (gp is not None and ebitda is not None) else None
    )

    waterfall = [
        {"label": "Revenue", "value": revenue, "kind": "total"},
        {"label": "COGS", "value": -cogs if cogs is not None else None, "kind": "delta"},
        {"label": "Gross Margin", "value": gp, "kind": "subtotal"},
        {"label": "Operating Costs", "value": -opex if opex is not None else None, "kind": "delta"},
        {"label": "EBITDA", "value": ebitda, "kind": "total"},
    ]

    bu_rows = db.execute(
        select(MisBuMonthly).where(
            and_(MisBuMonthly.company_id == company_code, MisBuMonthly.month_date == latest)
        )
    ).scalars().all()
    bu_breakdown = [
        {
            "bu_id": r.bu_id,
            "revenue_lacs": r.revenue_lacs,
            "gross_margin_lacs": r.gross_margin_lacs,
            "gross_margin_pct": r.gross_margin_pct,
            "ebitda_lacs": r.ebitda_lacs,
            "ebitda_pct": r.ebitda_pct,
        }
        for r in bu_rows
    ]

    channel_mix: dict[str, Decimal] = {ch: Decimal(0) for ch in CHANNEL_FIELDS}
    for r in bu_rows:
        for ch in CHANNEL_FIELDS:
            v = getattr(r, ch)
            if v is not None:
                channel_mix[ch] += v
    channel_mix = {k: v for k, v in channel_mix.items() if v != 0}

    latest_submission = db.execute(
        select(MisSubmission)
        .where(MisSubmission.company_id == company_code)
        .order_by(
            MisSubmission.period_year.desc(),
            MisSubmission.period_month.desc(),
            MisSubmission.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    anomaly_count = (
        db.execute(
            select(MisAnomaly).where(MisAnomaly.submission_id == latest_submission.id)
        ).scalars().all().__len__()
        if latest_submission is not None
        else 0
    )

    return {
        "company_code": company_code,
        "latest_month": latest,
        "kpis": kpis,
        "waterfall": waterfall,
        "bu_breakdown": bu_breakdown,
        "channel_mix": channel_mix,
        "latest_submission_id": (
            latest_submission.id if latest_submission is not None else None
        ),
        "anomaly_count": anomaly_count,
    }
