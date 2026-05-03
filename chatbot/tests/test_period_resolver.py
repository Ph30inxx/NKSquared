"""
Pure unit tests for financial_period_resolver.
No database or external services required — all logic is date arithmetic.
"""
import json
from datetime import date

import pytest

from chatbot.tools.mis import financial_period_resolver


pytestmark = pytest.mark.unit


# ── Helpers ───────────────────────────────────────────────────────────────────

def resolve(period: str) -> tuple[date, date]:
    data = json.loads(financial_period_resolver(period))
    return date.fromisoformat(data["start"]), date.fromisoformat(data["end"])


# ── Full fiscal years ─────────────────────────────────────────────────────────

def test_fy26_start():
    start, _ = resolve("FY26")
    assert start == date(2025, 4, 1)


def test_fy26_end():
    _, end = resolve("FY26")
    assert end == date(2026, 3, 31)


def test_fy25_range():
    start, end = resolve("FY25")
    assert start == date(2024, 4, 1)
    assert end   == date(2025, 3, 31)


def test_fy26_case_insensitive():
    lower_start, lower_end = resolve("fy26")
    upper_start, upper_end = resolve("FY26")
    assert lower_start == upper_start
    assert lower_end   == upper_end


# ── Quarters ─────────────────────────────────────────────────────────────────

def test_q1_fy26():
    start, end = resolve("Q1_FY26")
    assert start == date(2025, 4, 1)
    assert end   == date(2025, 6, 30)


def test_q2_fy26():
    start, end = resolve("Q2_FY26")
    assert start == date(2025, 7, 1)
    assert end   == date(2025, 9, 30)


def test_q3_fy26():
    start, end = resolve("Q3_FY26")
    assert start == date(2025, 10, 1)
    assert end   == date(2025, 12, 31)


def test_q4_fy26():
    start, end = resolve("Q4_FY26")
    assert start == date(2026, 1, 1)
    assert end   == date(2026, 3, 31)


def test_quarters_are_contiguous():
    """Q1 end + 1 day == Q2 start, etc."""
    from datetime import timedelta
    for q_cur, q_next in [("Q1_FY26", "Q2_FY26"), ("Q2_FY26", "Q3_FY26"), ("Q3_FY26", "Q4_FY26")]:
        _, end_cur  = resolve(q_cur)
        start_next, _ = resolve(q_next)
        assert end_cur + timedelta(days=1) == start_next


def test_quarters_cover_full_fy():
    """Q1–Q4 start and end match FY start and FY end."""
    fy_start, fy_end = resolve("FY26")
    q1_start, _      = resolve("Q1_FY26")
    _, q4_end        = resolve("Q4_FY26")
    assert q1_start == fy_start
    assert q4_end   == fy_end


# ── Half-years ────────────────────────────────────────────────────────────────

def test_h1_fy26():
    start, end = resolve("H1_FY26")
    assert start == date(2025, 4, 1)
    assert end   == date(2025, 9, 30)


def test_h2_fy26():
    start, end = resolve("H2_FY26")
    assert start == date(2025, 10, 1)
    assert end   == date(2026, 3, 31)


def test_h1_h2_contiguous_and_cover_fy():
    from datetime import timedelta
    _, h1_end   = resolve("H1_FY26")
    h2_start, _ = resolve("H2_FY26")
    fy_start, fy_end = resolve("FY26")
    h1_start, _      = resolve("H1_FY26")
    _, h2_end        = resolve("H2_FY26")

    assert h1_end + timedelta(days=1) == h2_start
    assert h1_start == fy_start
    assert h2_end   == fy_end


# ── Rolling windows ───────────────────────────────────────────────────────────

def test_last_3_months_end_is_last_day_of_prior_month():
    _, end = resolve("last_3_months")
    today = date.today()
    first_of_this_month = today.replace(day=1)
    from datetime import timedelta
    expected_end = first_of_this_month - timedelta(days=1)
    assert end == expected_end


def test_last_3_months_span_is_3_months():
    start, end = resolve("last_3_months")
    # start should be exactly 2 months before end's month (3 months total)
    from dateutil.relativedelta import relativedelta
    assert start == end.replace(day=1) - relativedelta(months=2)


def test_last_6_months_span_is_6_months():
    start, end = resolve("last_6_months")
    from dateutil.relativedelta import relativedelta
    assert start == end.replace(day=1) - relativedelta(months=5)


def test_last_3_and_last_6_share_same_end():
    _, end3 = resolve("last_3_months")
    _, end6 = resolve("last_6_months")
    assert end3 == end6


# ── Special keywords ──────────────────────────────────────────────────────────

def test_ytd_start_is_fy_start():
    start, end = resolve("ytd")
    today = date.today()
    # FY starts April. If today is before April the FY started in the prior year.
    expected_fy_start = (
        date(today.year, 4, 1)
        if today.month >= 4
        else date(today.year - 1, 4, 1)
    )
    assert start == expected_fy_start


def test_ytd_end_is_today():
    _, end = resolve("ytd")
    assert end == date.today()


def test_ytd_start_le_end():
    start, end = resolve("ytd")
    assert start <= end


def test_latest_is_last_complete_month():
    start, end = resolve("latest")
    today = date.today()
    from datetime import timedelta
    first_of_this  = today.replace(day=1)
    expected_end   = first_of_this - timedelta(days=1)
    expected_start = expected_end.replace(day=1)
    assert start == expected_start
    assert end   == expected_end


def test_latest_start_le_end():
    start, end = resolve("latest")
    assert start <= end


# ── Explicit ISO range passthrough ────────────────────────────────────────────

def test_explicit_range_passthrough():
    start, end = resolve("2025-04-01:2025-06-30")
    assert start == date(2025, 4, 1)
    assert end   == date(2025, 6, 30)


# ── Unknown input falls back gracefully ──────────────────────────────────────

def test_unknown_period_returns_a_valid_range():
    start, end = resolve("NONSENSE_VALUE")
    # Should return some FY range — both are valid dates and start < end
    assert isinstance(start, date)
    assert isinstance(end, date)
    assert start < end


# ── Return type is always valid JSON with start/end keys ─────────────────────

@pytest.mark.parametrize("period", [
    "FY26", "FY25", "Q1_FY26", "Q4_FY26", "H1_FY26", "H2_FY26",
    "last_3_months", "last_6_months", "ytd", "latest",
])
def test_always_returns_json_with_start_and_end(period):
    raw = financial_period_resolver(period)
    data = json.loads(raw)
    assert "start" in data
    assert "end"   in data
    # Both must be ISO-parseable
    date.fromisoformat(data["start"])
    date.fromisoformat(data["end"])
