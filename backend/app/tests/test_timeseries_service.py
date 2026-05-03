from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.mis import MisBuMonthly, MisMonthly, MisSubmission
from app.services import timeseries_service


def _add_monthly(db: Session, *, month: date, geo: str = "country_a", revenue=Decimal("100"), gp=Decimal("60"), ebitda=Decimal("20")) -> None:
    db.add(
        MisMonthly(
            company_id="company_t",
            month_date=month,
            geography=geo,
            revenue_lacs=revenue,
            cogs_lacs=revenue - gp,
            gross_margin_lacs=gp,
            gross_margin_pct=Decimal("0.6"),
            ebitda_lacs=ebitda,
        )
    )


def test_timeseries_consolidated_mom(db: Session) -> None:
    _add_monthly(db, month=date(2026, 2, 1), revenue=Decimal("100"))
    _add_monthly(db, month=date(2026, 3, 1), revenue=Decimal("150"))
    db.flush()

    out = timeseries_service.get_timeseries(db, "company_t", metrics=["revenue_lacs"])
    rev = out["series"]["revenue_lacs"]
    months = out["months"]
    feb_idx = months.index(date(2026, 2, 1))
    mar_idx = months.index(date(2026, 3, 1))
    assert rev[feb_idx]["value"] == Decimal("100")
    assert rev[mar_idx]["value"] == Decimal("150")
    assert rev[mar_idx]["mom_pct"] == Decimal("50")


def test_timeseries_geography_breakdown(db: Session) -> None:
    _add_monthly(db, month=date(2026, 3, 1), geo="country_a", revenue=Decimal("100"))
    _add_monthly(db, month=date(2026, 3, 1), geo="city_z", revenue=Decimal("50"))
    db.flush()
    out = timeseries_service.get_timeseries(
        db, "company_t", metrics=["revenue_lacs"], breakdown="geography"
    )
    series = out["series"]["revenue_lacs"]
    assert set(series.keys()) == {"country_a", "city_z"}


def test_summary_returns_none_when_no_data(db: Session) -> None:
    assert timeseries_service.get_summary(db, "company_zz") is None


def test_summary_basic_shape(db: Session) -> None:
    _add_monthly(db, month=date(2026, 2, 1), revenue=Decimal("100"))
    _add_monthly(db, month=date(2026, 3, 1), revenue=Decimal("150"))
    db.add(
        MisBuMonthly(
            company_id="company_t",
            bu_id="bu_1",
            month_date=date(2026, 3, 1),
            revenue_lacs=Decimal("150"),
            channel_dine_in_lacs=Decimal("80"),
            channel_aggregator_a_lacs=Decimal("70"),
        )
    )
    db.flush()
    out = timeseries_service.get_summary(db, "company_t")
    assert out is not None
    assert out["latest_month"] == date(2026, 3, 1)
    assert out["kpis"]["revenue_lacs"]["value"] == Decimal("150")
    labels = [s["label"] for s in out["waterfall"]]
    assert labels == ["Revenue", "COGS", "Gross Margin", "Operating Costs", "EBITDA"]
    assert "channel_dine_in_lacs" in out["channel_mix"]
