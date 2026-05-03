"""
Shared fixtures for the chatbot test suite.

All tests run inside Docker where both PostgreSQL and the Azure OpenAI
environment variables are always available. Nothing is skipped or mocked.
"""
from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import psycopg2
import psycopg2.extras
import pytest


# ── DB URL ────────────────────────────────────────────────────────────────────

def _db_url() -> str:
    raw = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://nksquared_user:dev@postgres:5432/nksquared",
    )
    return raw.replace("postgresql+psycopg://", "postgresql://")


def _cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)


# ── Session-scoped connection (one connection per test session) ────────────────

@pytest.fixture(scope="session")
def pg():
    """Single psycopg2 connection reused across the whole test session."""
    conn = psycopg2.connect(_db_url())
    yield conn
    conn.close()


# ── Test data identifiers ─────────────────────────────────────────────────────

_TEST_COMPANY_NAME = "__CHATBOT_TEST__"
_TEST_MIS_CID      = "__test__"
_TEST_VQ_PREFIX    = "__TEST_VQ__"


# ── Test data fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def test_company(pg):
    """
    Insert a portfolio company with two transactions and one valuation.
    Yields a dict with 'id', 'display_name', 'moic'.
    Cleans up all related rows on teardown.
    """
    conn = psycopg2.connect(_db_url())
    cur  = _cursor(conn)

    cur.execute("""
        INSERT INTO portfolio_companies
            (company_name, display_name,
             investment_value_cr, current_value_cr, moic, irr,
             currency, is_active, reporting_frequency,
             portfolio_type, investment_status, portfolio_status,
             asset_class, sector)
        VALUES
            (%s, %s, %s, %s, %s, %s,
             'INR', true, 'Monthly',
             'Entity_D_Core', 'Active', 'Unrealized',
             'Direct_Equity', 'Technology')
        RETURNING id
    """, (
        _TEST_COMPANY_NAME, _TEST_COMPANY_NAME,
        Decimal("-100.00"), Decimal("184.00"), Decimal("1.84"), Decimal("0.22"),
    ))
    company_id = cur.fetchone()["id"]
    conn.commit()

    cur.execute("""
        INSERT INTO portfolio_transactions
            (company_id, transaction_date, transaction_type,
             amount_cr, original_currency, original_amount, amount_inr_cr)
        VALUES
            (%s, %s, 'Investment', -70.00, 'INR', 70.00, -70.00),
            (%s, %s, 'Follow_on',  -30.00, 'INR', 30.00, -30.00)
    """, (
        company_id, date(2023, 4, 1),
        company_id, date(2024, 1, 1),
    ))
    conn.commit()

    cur.execute("""
        INSERT INTO valuations
            (company_id, valuation_date, post_money_valuation_cr, currency, source)
        VALUES (%s, %s, 920.00, 'INR', 'Internal')
    """, (company_id, date(2024, 6, 1)))
    conn.commit()

    yield {
        "id":           company_id,
        "display_name": _TEST_COMPANY_NAME,
        "moic":         Decimal("1.84"),
    }

    cur.execute("DELETE FROM valuations             WHERE company_id = %s", (company_id,))
    cur.execute("DELETE FROM portfolio_transactions WHERE company_id = %s", (company_id,))
    cur.execute("DELETE FROM portfolio_companies    WHERE id = %s",          (company_id,))
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def test_company_low_moic(pg):
    """A portfolio company with MOIC < 0.95 — triggers HIGH alerts."""
    conn = psycopg2.connect(_db_url())
    cur  = _cursor(conn)

    cur.execute("""
        INSERT INTO portfolio_companies
            (company_name, display_name,
             investment_value_cr, current_value_cr, moic,
             currency, is_active, reporting_frequency,
             investment_status, portfolio_status, sector)
        VALUES (%s, %s, -200.00, 150.00, 0.75,
                'INR', true, 'Monthly',
                'Active', 'Unrealized', 'Technology')
        RETURNING id
    """, ("__CHATBOT_TEST_LOW__", "__CHATBOT_TEST_LOW__"))
    company_id = cur.fetchone()["id"]
    conn.commit()

    yield {"id": company_id}

    cur.execute("DELETE FROM portfolio_companies WHERE id = %s", (company_id,))
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def test_mis_data(pg):
    """
    Two months of consolidated mis_monthly (Oct + Nov 2025) and one BU row
    for the __test__ company. Cleans up on teardown.
    """
    conn = psycopg2.connect(_db_url())
    cur  = _cursor(conn)

    rows = [
        # month_date, revenue, cogs, gm, gm_pct, opex, ebitda, ebitda_pct
        (date(2025, 10, 1), 500.00, 200.00, 300.00, 0.60, 180.00, 120.00, 0.24),
        (date(2025, 11, 1), 540.00, 210.00, 330.00, 0.61, 185.00, 145.00, 0.27),
    ]
    for r in rows:
        cur.execute("""
            INSERT INTO mis_monthly
                (company_id, month_date, fiscal_year, quarter, geography, currency,
                 total_income_lacs, cogs_lacs, gross_margin_lacs, gross_margin_pct,
                 total_operating_costs_lacs, ebitda_lacs, ebitda_pct)
            VALUES
                (%s, %s, 'FY26', 'Q3', 'consolidated', 'INR',
                 %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (company_id, month_date, geography) DO NOTHING
        """, (_TEST_MIS_CID, *r))
    conn.commit()

    cur.execute("""
        INSERT INTO mis_bu_monthly
            (company_id, bu_id, month_date, fiscal_year, quarter, currency,
             revenue_lacs, ebitda_lacs, gross_margin_pct)
        VALUES (%s, 'BU_01', %s, 'FY26', 'Q3', 'INR', 540.00, 145.00, 0.61)
        ON CONFLICT (company_id, bu_id, month_date) DO NOTHING
    """, (_TEST_MIS_CID, date(2025, 11, 1)))
    conn.commit()

    yield {"company_id": _TEST_MIS_CID}

    cur.execute("DELETE FROM mis_bu_monthly WHERE company_id = %s", (_TEST_MIS_CID,))
    cur.execute("DELETE FROM mis_monthly     WHERE company_id = %s", (_TEST_MIS_CID,))
    conn.commit()
    cur.close()
    conn.close()


@pytest.fixture
def clean_validated_queries(pg):
    """Delete test-prefixed validated query rows before and after each test."""
    conn = psycopg2.connect(_db_url())
    cur  = _cursor(conn)

    cur.execute(
        "DELETE FROM nk_validated_queries WHERE question LIKE %s",
        (f"{_TEST_VQ_PREFIX}%",),
    )
    conn.commit()

    yield _TEST_VQ_PREFIX

    cur.execute(
        "DELETE FROM nk_validated_queries WHERE question LIKE %s",
        (f"{_TEST_VQ_PREFIX}%",),
    )
    conn.commit()
    cur.close()
    conn.close()
