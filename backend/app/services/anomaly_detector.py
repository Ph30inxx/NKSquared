"""MIS anomaly detector — implements the 10 rules from §4.6 of the implementation plan.

Anomalies are advisory: they surface in the MIS review panel but never block submission
or approval. The detector runs once on file upload (so analysts see issues before
deciding) and again on approve (DB state may have changed).

Each rule yields zero or more `AnomalyRecord` instances; the caller persists them.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.forex import ForexRate
from app.models.mis import MisMonthly, MisSubmission
from app.services.fx_service import _FALLBACK_WINDOW
from app.services.sample_loader.mis_loader_v1 import (
    MisBuMonthlyRow,
    MisMonthlyRow,
    ParsedMisSubmission,
)


SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"

# Thresholds from §4.6.
_MOM_REVENUE_THRESHOLD = Decimal("0.30")
_MOM_EBITDA_MAGNITUDE_THRESHOLD = Decimal("0.20")
_GM_DRIFT_THRESHOLD_PP = Decimal("5")
_ARITHMETIC_TOLERANCE = Decimal("0.01")
_CHANNEL_TOLERANCE = Decimal("0.01")
_LACS_REVENUE_SANITY_CEILING = Decimal("100000")  # >100,000 lacs ⇒ likely Cr (1000+ Cr)


@dataclass
class AnomalyRecord:
    rule_code: str
    severity: str
    message: str
    metric: str | None = None
    period_year: int | None = None
    period_month: int | None = None
    geography: str | None = None
    bu_id: str | None = None


def detect(
    db: Session,
    submission: MisSubmission,
    parsed: ParsedMisSubmission,
) -> list[AnomalyRecord]:
    """Run all 10 rules. Returns a flat list (caller persists)."""
    findings: list[AnomalyRecord] = []
    findings.extend(_rule_missing_required_lines(parsed))
    findings.extend(_rule_arithmetic_gp(parsed))
    findings.extend(_rule_future_dated(parsed))
    findings.extend(_rule_unit_mismatch(parsed))
    findings.extend(_rule_channel_sum_mismatch(parsed))
    findings.extend(_rule_mom_revenue_swing(db, submission, parsed))
    findings.extend(_rule_mom_ebitda_flip(db, submission, parsed))
    findings.extend(_rule_gm_drift(db, submission, parsed))
    findings.extend(_rule_fx_stale(db, submission, parsed))
    findings.extend(_rule_duplicate_submission(db, submission))
    return findings


# ----------------------------------------------------------------------------
# Row-level rules (no DB lookup)
# ----------------------------------------------------------------------------


def _rule_missing_required_lines(parsed: ParsedMisSubmission) -> list[AnomalyRecord]:
    out: list[AnomalyRecord] = []
    for r in parsed.monthly_rows:
        missing: list[str] = []
        if r.revenue_lacs is None:
            missing.append("revenue")
        if r.cogs_lacs is None:
            missing.append("COGS")
        if r.ebitda_lacs is None:
            missing.append("EBITDA")
        if missing:
            out.append(
                AnomalyRecord(
                    rule_code="MISSING_REQUIRED_LINE",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{r.month_date:%b %Y} ({r.geography}): missing "
                        f"{', '.join(missing)}"
                    ),
                    metric=missing[0],
                    period_year=r.month_date.year,
                    period_month=r.month_date.month,
                    geography=r.geography,
                )
            )
    return out


def _rule_arithmetic_gp(parsed: ParsedMisSubmission) -> list[AnomalyRecord]:
    out: list[AnomalyRecord] = []
    for r in parsed.monthly_rows:
        if r.revenue_lacs is None or r.cogs_lacs is None or r.gross_margin_lacs is None:
            continue
        if r.revenue_lacs == 0:
            continue
        expected = r.revenue_lacs - r.cogs_lacs
        diff = abs(r.gross_margin_lacs - expected)
        if diff / abs(r.revenue_lacs) > _ARITHMETIC_TOLERANCE:
            out.append(
                AnomalyRecord(
                    rule_code="ARITHMETIC_GP",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"{r.month_date:%b %Y} ({r.geography}): "
                        f"GP {r.gross_margin_lacs} ≠ Revenue {r.revenue_lacs} − "
                        f"COGS {r.cogs_lacs} (diff {diff:.2f} L > 1%)"
                    ),
                    metric="gross_margin_lacs",
                    period_year=r.month_date.year,
                    period_month=r.month_date.month,
                    geography=r.geography,
                )
            )
    return out


def _rule_future_dated(parsed: ParsedMisSubmission) -> list[AnomalyRecord]:
    today = date.today()
    seen: set[date] = set()
    out: list[AnomalyRecord] = []
    for r in parsed.monthly_rows:
        if r.month_date > today and r.month_date not in seen:
            seen.add(r.month_date)
            out.append(
                AnomalyRecord(
                    rule_code="FUTURE_DATED_ROW",
                    severity=SEVERITY_ERROR,
                    message=f"Row dated {r.month_date:%b %Y} is in the future.",
                    period_year=r.month_date.year,
                    period_month=r.month_date.month,
                    geography=r.geography,
                )
            )
    return out


def _rule_unit_mismatch(parsed: ParsedMisSubmission) -> list[AnomalyRecord]:
    """Heuristic: if a 'lacs' submission has any monthly revenue > 100,000 L, the
    file is probably in Cr or raw rupees and the unit was misread.
    """
    for r in parsed.monthly_rows:
        if r.revenue_lacs is not None and abs(r.revenue_lacs) > _LACS_REVENUE_SANITY_CEILING:
            return [
                AnomalyRecord(
                    rule_code="UNIT_MISMATCH",
                    severity=SEVERITY_ERROR,
                    message=(
                        f"Revenue {r.revenue_lacs} for {r.month_date:%b %Y} "
                        f"({r.geography}) exceeds {_LACS_REVENUE_SANITY_CEILING} L — "
                        "unit may be Cr or raw rupees instead of Lacs."
                    ),
                    metric="revenue_lacs",
                    period_year=r.month_date.year,
                    period_month=r.month_date.month,
                    geography=r.geography,
                )
            ]
    return []


def _rule_channel_sum_mismatch(parsed: ParsedMisSubmission) -> list[AnomalyRecord]:
    out: list[AnomalyRecord] = []
    channel_fields = (
        "channel_dine_in_lacs",
        "channel_aggregator_a_lacs",
        "channel_aggregator_b_lacs",
        "channel_aggregator_d_lacs",
        "channel_catering_lacs",
        "channel_franchise_lacs",
    )
    for r in parsed.bu_rows:
        revenue = r.revenue_lacs
        if revenue is None or revenue == 0:
            continue
        present = [getattr(r, f) for f in channel_fields if getattr(r, f) is not None]
        if not present:
            continue
        total = sum(present, Decimal("0"))
        if abs(total - revenue) / abs(revenue) > _CHANNEL_TOLERANCE:
            out.append(
                AnomalyRecord(
                    rule_code="CHANNEL_SUM_MISMATCH",
                    severity=SEVERITY_WARNING,
                    message=(
                        f"{r.month_date:%b %Y} BU {r.bu_id}: channel sum "
                        f"{total:.2f} L ≠ revenue {revenue:.2f} L (>1%)."
                    ),
                    metric="revenue_lacs",
                    period_year=r.month_date.year,
                    period_month=r.month_date.month,
                    bu_id=r.bu_id,
                )
            )
    return out


# ----------------------------------------------------------------------------
# DB-aware rules (need prior periods or other submissions)
# ----------------------------------------------------------------------------


def _rule_mom_revenue_swing(
    db: Session, submission: MisSubmission, parsed: ParsedMisSubmission
) -> list[AnomalyRecord]:
    return _mom_check(
        db,
        submission,
        parsed,
        metric="revenue_lacs",
        rule_code="MOM_REVENUE_SWING",
        threshold=_MOM_REVENUE_THRESHOLD,
        message_fmt=lambda prev, curr, geo, m: (
            f"{m:%b %Y} ({geo}): revenue swung {((curr - prev) / abs(prev) * 100):+.1f}% "
            f"vs prior month (>30%)."
        ),
    )


def _rule_mom_ebitda_flip(
    db: Session, submission: MisSubmission, parsed: ParsedMisSubmission
) -> list[AnomalyRecord]:
    out: list[AnomalyRecord] = []
    by_geo = _group_monthly_by_geo(parsed.monthly_rows)
    for geo, rows_in_submission in by_geo.items():
        prior_lookup = _prior_monthly_map(db, submission, geo, metric="ebitda_lacs")
        rows_in_submission_sorted = sorted(rows_in_submission, key=lambda r: r.month_date)
        for r in rows_in_submission_sorted:
            curr = r.ebitda_lacs
            if curr is None:
                continue
            prev = _prev_value(r.month_date, rows_in_submission_sorted, prior_lookup, "ebitda_lacs")
            if prev is None or prev == 0:
                continue
            sign_flipped = (prev > 0 and curr < 0) or (prev < 0 and curr > 0)
            if not sign_flipped:
                continue
            magnitude = abs(curr - prev) / abs(prev)
            if magnitude > _MOM_EBITDA_MAGNITUDE_THRESHOLD:
                out.append(
                    AnomalyRecord(
                        rule_code="MOM_EBITDA_FLIP",
                        severity=SEVERITY_WARNING,
                        message=(
                            f"{r.month_date:%b %Y} ({geo}): EBITDA flipped sign "
                            f"({prev:.2f} → {curr:.2f}, "
                            f"{magnitude * 100:.0f}% magnitude)."
                        ),
                        metric="ebitda_lacs",
                        period_year=r.month_date.year,
                        period_month=r.month_date.month,
                        geography=geo,
                    )
                )
    return out


def _rule_gm_drift(
    db: Session, submission: MisSubmission, parsed: ParsedMisSubmission
) -> list[AnomalyRecord]:
    out: list[AnomalyRecord] = []
    by_geo = _group_monthly_by_geo(parsed.monthly_rows)
    for geo, rows_in_submission in by_geo.items():
        prior_lookup = _prior_monthly_map(db, submission, geo, metric="gross_margin_pct")
        rows_in_submission_sorted = sorted(rows_in_submission, key=lambda r: r.month_date)
        for r in rows_in_submission_sorted:
            if r.gross_margin_pct is None:
                continue
            trailing = _trailing_values(
                r.month_date, rows_in_submission_sorted, prior_lookup, "gross_margin_pct", n=3
            )
            if len(trailing) < 1:
                continue
            avg = Decimal(str(mean([float(v) for v in trailing])))
            curr_pct = r.gross_margin_pct * Decimal(100)
            avg_pct = avg * Decimal(100)
            drift = abs(curr_pct - avg_pct)
            if drift > _GM_DRIFT_THRESHOLD_PP:
                out.append(
                    AnomalyRecord(
                        rule_code="GM_DRIFT",
                        severity=SEVERITY_WARNING,
                        message=(
                            f"{r.month_date:%b %Y} ({geo}): GM% {curr_pct:.1f}% drifted "
                            f"{drift:.1f}pp from {len(trailing)}-month avg {avg_pct:.1f}%."
                        ),
                        metric="gross_margin_pct",
                        period_year=r.month_date.year,
                        period_month=r.month_date.month,
                        geography=geo,
                    )
                )
    return out


def _rule_fx_stale(
    db: Session, submission: MisSubmission, parsed: ParsedMisSubmission
) -> list[AnomalyRecord]:
    currencies = {(r.currency or "INR").upper() for r in parsed.monthly_rows}
    foreign = {c for c in currencies if c and c != "INR"}
    if not foreign:
        return []
    latest_period = max((r.month_date for r in parsed.monthly_rows), default=None)
    if latest_period is None:
        return []
    out: list[AnomalyRecord] = []
    for ccy in foreign:
        latest_rate = db.execute(
            select(ForexRate)
            .where(
                ForexRate.from_currency == ccy,
                ForexRate.to_currency == "INR",
                ForexRate.effective_date <= latest_period,
            )
            .order_by(ForexRate.effective_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_rate is None or latest_period - latest_rate.effective_date > _FALLBACK_WINDOW:
            stale_days = (
                (latest_period - latest_rate.effective_date).days if latest_rate else None
            )
            out.append(
                AnomalyRecord(
                    rule_code="FX_RATE_STALE",
                    severity=SEVERITY_WARNING,
                    message=(
                        f"No FX rate {ccy}→INR within 30 days of {latest_period:%b %Y}"
                        + (f" (most recent is {stale_days} days old)." if stale_days else ".")
                    ),
                    metric="fx_rate",
                    period_year=latest_period.year,
                    period_month=latest_period.month,
                )
            )
    return out


def _rule_duplicate_submission(
    db: Session, submission: MisSubmission
) -> list[AnomalyRecord]:
    other = db.execute(
        select(MisSubmission).where(
            and_(
                MisSubmission.company_id == submission.company_id,
                MisSubmission.period_year == submission.period_year,
                MisSubmission.period_month == submission.period_month,
                MisSubmission.id != submission.id,
                MisSubmission.status == "Approved",
            )
        )
    ).scalar_one_or_none()
    if other is None:
        return []
    return [
        AnomalyRecord(
            rule_code="DUPLICATE_SUBMISSION",
            severity=SEVERITY_ERROR,
            message=(
                f"Submission #{other.id} for {submission.company_id} "
                f"{submission.period_year}-{submission.period_month:02d} is already approved."
            ),
            period_year=submission.period_year,
            period_month=submission.period_month,
        )
    ]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _group_monthly_by_geo(
    rows: Iterable[MisMonthlyRow],
) -> dict[str, list[MisMonthlyRow]]:
    out: dict[str, list[MisMonthlyRow]] = {}
    for r in rows:
        out.setdefault(r.geography, []).append(r)
    return out


def _prior_monthly_map(
    db: Session, submission: MisSubmission, geography: str, *, metric: str
) -> dict[date, Decimal]:
    """Look up prior-period values from `mis_monthly` for the same company+geo,
    excluding the current submission's rows.
    """
    rows = db.execute(
        select(MisMonthly).where(
            and_(
                MisMonthly.company_id == submission.company_id,
                MisMonthly.geography == geography,
                or_(
                    MisMonthly.submission_id.is_(None),
                    MisMonthly.submission_id != submission.id,
                ),
            )
        )
    ).scalars().all()
    out: dict[date, Decimal] = {}
    for row in rows:
        v = getattr(row, metric, None)
        if v is not None and row.month_date is not None:
            out[row.month_date] = v
    return out


def _prev_month(d: date) -> date:
    """First-of-prior-month."""
    if d.month == 1:
        return date(d.year - 1, 12, 1)
    return date(d.year, d.month - 1, 1)


def _prev_value(
    current: date,
    rows_in_submission: list[MisMonthlyRow],
    prior_lookup: dict[date, Decimal],
    metric: str,
) -> Decimal | None:
    target = _prev_month(current)
    for r in rows_in_submission:
        if r.month_date == target:
            v = getattr(r, metric, None)
            if v is not None:
                return v
    return prior_lookup.get(target)


def _mom_check(
    db: Session,
    submission: MisSubmission,
    parsed: ParsedMisSubmission,
    *,
    metric: str,
    rule_code: str,
    threshold: Decimal,
    message_fmt,
) -> list[AnomalyRecord]:
    out: list[AnomalyRecord] = []
    by_geo = _group_monthly_by_geo(parsed.monthly_rows)
    for geo, rows in by_geo.items():
        prior_lookup = _prior_monthly_map(db, submission, geo, metric=metric)
        rows_sorted = sorted(rows, key=lambda r: r.month_date)
        for r in rows_sorted:
            curr = getattr(r, metric, None)
            if curr is None:
                continue
            prev = _prev_value(r.month_date, rows_sorted, prior_lookup, metric)
            if prev is None or prev == 0:
                continue
            change = abs(curr - prev) / abs(prev)
            if change > threshold:
                out.append(
                    AnomalyRecord(
                        rule_code=rule_code,
                        severity=SEVERITY_WARNING,
                        message=message_fmt(prev, curr, geo, r.month_date),
                        metric=metric,
                        period_year=r.month_date.year,
                        period_month=r.month_date.month,
                        geography=geo,
                    )
                )
    return out


def _trailing_values(
    current: date,
    rows_in_submission: list[MisMonthlyRow],
    prior_lookup: dict[date, Decimal],
    metric: str,
    *,
    n: int,
) -> list[Decimal]:
    """Last `n` values strictly before `current`, drawn from this submission and DB."""
    out: list[Decimal] = []
    cursor = _prev_month(current)
    for _ in range(n):
        v: Decimal | None = None
        for r in rows_in_submission:
            if r.month_date == cursor:
                rv = getattr(r, metric, None)
                if rv is not None:
                    v = rv
                break
        if v is None:
            v = prior_lookup.get(cursor)
        if v is not None:
            out.append(v)
        cursor = _prev_month(cursor)
    return out


__all__ = [
    "AnomalyRecord",
    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "detect",
]
