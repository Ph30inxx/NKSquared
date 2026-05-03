from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.forex import ForexRate
from app.models.mis import MisMonthly, MisSubmission
from app.services import anomaly_detector
from app.services.sample_loader.mis_loader_v1 import (
    MisBuMonthlyRow,
    MisMonthlyRow,
    ParsedMisSubmission,
)


def _row(
    *,
    month: date = date(2026, 3, 1),
    geo: str = "country_a",
    revenue: Decimal | None = Decimal("100"),
    cogs: Decimal | None = Decimal("40"),
    gp: Decimal | None = Decimal("60"),
    gp_pct: Decimal | None = Decimal("0.6"),
    ebitda: Decimal | None = Decimal("20"),
    company_id: str = "company_t",
) -> MisMonthlyRow:
    return MisMonthlyRow(
        company_id=company_id,
        month_date=month,
        fiscal_year="FY26",
        quarter="Q4",
        geography=geo,
        revenue_lacs=revenue,
        cogs_lacs=cogs,
        gross_margin_lacs=gp,
        gross_margin_pct=gp_pct,
        ebitda_lacs=ebitda,
    )


def _submission(db: Session, *, company_id="company_t", year=2026, month=3) -> MisSubmission:
    sub = MisSubmission(
        company_id=company_id,
        period_year=year,
        period_month=month,
        fiscal_year=f"FY{(year + (1 if month >= 4 else 0)) % 100:02d}",
        status="Submitted",
    )
    db.add(sub)
    db.flush()
    return sub


def _parsed(rows: list[MisMonthlyRow], bu_rows: list[MisBuMonthlyRow] | None = None, *, year=2026, month=3) -> ParsedMisSubmission:
    return ParsedMisSubmission(
        company_id=rows[0].company_id if rows else "company_t",
        period_year=year,
        period_month=month,
        fiscal_year="FY26",
        source_file_name="t.xlsx",
        monthly_rows=rows,
        bu_rows=bu_rows or [],
    )


def test_missing_required_lines_flags_each_missing(db: Session) -> None:
    sub = _submission(db)
    parsed = _parsed([_row(revenue=None, cogs=None, ebitda=None, gp=None)])
    out = anomaly_detector.detect(db, sub, parsed)
    codes = {a.rule_code for a in out}
    assert "MISSING_REQUIRED_LINE" in codes
    assert all(a.severity == "error" for a in out if a.rule_code == "MISSING_REQUIRED_LINE")


def test_arithmetic_gp_violation(db: Session) -> None:
    sub = _submission(db)
    parsed = _parsed([_row(gp=Decimal("75"))])  # GP should be 60
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "ARITHMETIC_GP" for a in out)


def test_arithmetic_gp_within_tolerance(db: Session) -> None:
    sub = _submission(db)
    parsed = _parsed([_row(gp=Decimal("60.5"))])  # 0.5% drift, within 1%
    out = anomaly_detector.detect(db, sub, parsed)
    assert not any(a.rule_code == "ARITHMETIC_GP" for a in out)


def test_future_dated_row(db: Session) -> None:
    sub = _submission(db)
    future = date.today().replace(day=1) + timedelta(days=400)
    parsed = _parsed([_row(month=date(future.year, future.month, 1))])
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "FUTURE_DATED_ROW" for a in out)


def test_unit_mismatch_excessive_lacs(db: Session) -> None:
    sub = _submission(db)
    # 200,000 lacs = 200 Cr × 100 = wildly off; flagged.
    parsed = _parsed([_row(revenue=Decimal("250000"), cogs=Decimal("100000"), gp=Decimal("150000"), ebitda=Decimal("100000"))])
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "UNIT_MISMATCH" for a in out)


def test_channel_sum_mismatch(db: Session) -> None:
    sub = _submission(db)
    bu = MisBuMonthlyRow(
        company_id="company_t",
        bu_id="bu_1",
        month_date=date(2026, 3, 1),
        fiscal_year="FY26",
        quarter="Q4",
        revenue_lacs=Decimal("100"),
        channel_dine_in_lacs=Decimal("60"),
        channel_aggregator_a_lacs=Decimal("20"),
    )  # sum = 80, revenue = 100 → 20% gap
    parsed = _parsed([_row()], [bu])
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "CHANNEL_SUM_MISMATCH" for a in out)


def test_mom_revenue_swing_via_db(db: Session) -> None:
    # Pre-existing approved row in mis_monthly for the prior period.
    prior = MisMonthly(
        company_id="company_t",
        month_date=date(2026, 2, 1),
        fiscal_year="FY26",
        quarter="Q4",
        geography="country_a",
        currency="INR",
        revenue_lacs=Decimal("100"),
        gross_margin_pct=Decimal("0.6"),
        ebitda_lacs=Decimal("10"),
    )
    db.add(prior)
    db.flush()
    sub = _submission(db)
    parsed = _parsed([_row(revenue=Decimal("200"), cogs=Decimal("80"), gp=Decimal("120"), ebitda=Decimal("40"))])  # +100% swing
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "MOM_REVENUE_SWING" for a in out)


def test_mom_ebitda_flip_via_db(db: Session) -> None:
    prior = MisMonthly(
        company_id="company_t",
        month_date=date(2026, 2, 1),
        geography="country_a",
        revenue_lacs=Decimal("100"),
        cogs_lacs=Decimal("40"),
        gross_margin_lacs=Decimal("60"),
        gross_margin_pct=Decimal("0.6"),
        ebitda_lacs=Decimal("10"),
    )
    db.add(prior)
    db.flush()
    sub = _submission(db)
    parsed = _parsed([_row(ebitda=Decimal("-15"))])  # flipped sign, magnitude > 20%
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "MOM_EBITDA_FLIP" for a in out)


def test_gm_drift_flagged(db: Session) -> None:
    # Three trailing months of GM% ≈ 0.60; current month jumps to 0.70 (10pp drift).
    for m in (date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)):
        db.add(
            MisMonthly(
                company_id="company_t",
                month_date=m,
                geography="country_a",
                revenue_lacs=Decimal("100"),
                cogs_lacs=Decimal("40"),
                gross_margin_lacs=Decimal("60"),
                gross_margin_pct=Decimal("0.6"),
                ebitda_lacs=Decimal("10"),
            )
        )
    db.flush()
    sub = _submission(db)
    parsed = _parsed([_row(gp_pct=Decimal("0.70"), gp=Decimal("60"))])
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "GM_DRIFT" for a in out)


def test_fx_rate_stale(db: Session) -> None:
    # Latest period is March 2026; only FX rate available is from 2025-12.
    db.add(
        ForexRate(
            from_currency="USD",
            to_currency="INR",
            effective_date=date(2025, 12, 1),
            rate=Decimal("82.5"),
        )
    )
    db.flush()
    sub = _submission(db)
    rows = [_row()]
    rows[0].currency = "USD"
    parsed = _parsed(rows)
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "FX_RATE_STALE" for a in out)


def test_duplicate_submission(db: Session) -> None:
    other = MisSubmission(
        company_id="company_t",
        period_year=2026,
        period_month=3,
        fiscal_year="FY26",
        status="Approved",
    )
    db.add(other)
    db.flush()
    # Persist `sub` with a different period to avoid the unique constraint,
    # then mutate the in-memory period to match `other` before running detect.
    sub = _submission(db, year=2026, month=4)
    sub.period_month = 3
    parsed = _parsed([_row()])
    out = anomaly_detector.detect(db, sub, parsed)
    assert any(a.rule_code == "DUPLICATE_SUBMISSION" for a in out)


def test_clean_submission_yields_no_anomalies(db: Session) -> None:
    sub = _submission(db)
    parsed = _parsed([_row()])
    out = anomaly_detector.detect(db, sub, parsed)
    assert out == []
