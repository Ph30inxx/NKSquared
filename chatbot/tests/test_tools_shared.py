"""
Tests for chatbot/tools/shared.py:
  execute_safe_query, forex_converter, find_similar_query, save_validated_query.

DB-dependent tests are marked `integration` and auto-skip if Postgres is down.
"""
import json

import pytest

from chatbot.tools.shared import (
    execute_safe_query,
    find_similar_query,
    forex_converter,
    save_validated_query,
)

pytestmark = pytest.mark.integration


# ── execute_safe_query ────────────────────────────────────────────────────────

class TestExecuteSafeQuery:

    def test_non_select_is_blocked(self, pg):
        result = json.loads(execute_safe_query("DELETE FROM portfolio_companies"))
        assert "error" in result
        assert "SELECT" in result["error"]

    def test_insert_is_blocked(self, pg):
        result = json.loads(execute_safe_query(
            "INSERT INTO portfolio_companies (company_name) VALUES ('x')"
        ))
        assert "error" in result

    def test_unknown_table_is_blocked(self, pg):
        result = json.loads(execute_safe_query("SELECT * FROM pg_shadow"))
        assert "error" in result

    def test_valid_query_returns_rows_and_count(self, pg):
        result = json.loads(execute_safe_query(
            "SELECT 1 AS val FROM portfolio_companies LIMIT 1"
        ))
        assert "error" not in result
        assert "rows" in result
        assert "row_count" in result
        assert isinstance(result["rows"], list)

    def test_row_count_matches_rows_length(self, pg):
        result = json.loads(execute_safe_query(
            "SELECT id FROM portfolio_companies LIMIT 10"
        ))
        assert result["row_count"] == len(result["rows"])

    def test_trailing_semicolon_is_tolerated(self, pg):
        result = json.loads(execute_safe_query(
            "SELECT COUNT(*) AS n FROM forex_rates;"
        ))
        assert "error" not in result
        assert result["rows"][0]["n"] >= 0

    def test_row_limit_is_enforced(self, pg):
        # Ask for more than the cap; we should get at most SAFE_QUERY_ROW_LIMIT
        from chatbot.config import SAFE_QUERY_ROW_LIMIT
        result = json.loads(execute_safe_query(
            f"SELECT generate_series(1, {SAFE_QUERY_ROW_LIMIT + 100}) AS n "
            f"FROM portfolio_companies LIMIT {SAFE_QUERY_ROW_LIMIT + 100}"
        ))
        # The subquery wrapping enforces the cap even if the inner query asks for more
        if "error" not in result:
            assert result["row_count"] <= SAFE_QUERY_ROW_LIMIT

    def test_query_against_nk_validated_queries_is_allowed(self, pg):
        result = json.loads(execute_safe_query(
            "SELECT COUNT(*) AS n FROM nk_validated_queries"
        ))
        assert "error" not in result

    def test_syntax_error_returns_error_json(self, pg):
        result = json.loads(execute_safe_query(
            "SELECT FROM WHERE INVALID"
        ))
        assert "error" in result


# ── forex_converter ───────────────────────────────────────────────────────────

class TestForexConverter:

    def test_same_currency_is_identity(self, pg):
        result = json.loads(forex_converter(100.0, "INR", "INR"))
        assert result["converted_amount"] == 100.0
        assert result["rate"]             == 1.0
        assert result["rate_date"]        is None

    def test_same_currency_case_insensitive(self, pg):
        result = json.loads(forex_converter(50.0, "inr", "INR"))
        assert result["converted_amount"] == 50.0

    def test_usd_to_inr_returns_positive_rate(self, pg):
        result = json.loads(forex_converter(1.0, "USD", "INR"))
        # Seeded data has USD → INR rates
        assert "error" not in result
        assert result["rate"] > 1.0          # 1 USD > 1 INR
        assert result["converted_amount"] > 1.0

    def test_aed_to_inr_returns_result(self, pg):
        result = json.loads(forex_converter(100.0, "AED", "INR"))
        assert "error" not in result
        assert result["converted_amount"] > 0

    def test_unknown_pair_returns_error(self, pg):
        result = json.loads(forex_converter(1.0, "JPY", "INR"))
        assert "error" in result

    def test_as_of_date_accepted(self, pg):
        # Just verify it does not raise — seeded rates cover 2024+
        result = json.loads(forex_converter(1.0, "USD", "INR", as_of_date="2025-01-01"))
        assert "error" not in result
        assert result["rate_date"] is not None

    def test_result_has_expected_keys(self, pg):
        result = json.loads(forex_converter(10.0, "USD", "INR"))
        for key in ("converted_amount", "rate", "from_currency", "to_currency", "rate_date", "note"):
            assert key in result

    def test_conversion_is_multiplicative(self, pg):
        single = json.loads(forex_converter(1.0, "USD", "INR"))
        double = json.loads(forex_converter(2.0, "USD", "INR"))
        if "error" not in single and "error" not in double:
            assert abs(double["converted_amount"] - 2 * single["converted_amount"]) < 0.01


# ── save_validated_query + find_similar_query ─────────────────────────────────

class TestValidatedQueryRoundtrip:

    def test_save_returns_confirmation(self, pg, clean_validated_queries):
        prefix = clean_validated_queries
        msg = save_validated_query(
            question=f"{prefix} What is overall MOIC",
            sql_query="SELECT moic FROM portfolio_companies LIMIT 1",
            explanation="Fetches MOIC from portfolio_companies.",
            tables_used="portfolio_companies",
        )
        assert "saved" in msg.lower() or "knowledge" in msg.lower()

    def test_duplicate_is_rejected(self, pg, clean_validated_queries):
        prefix = clean_validated_queries
        q = f"{prefix} What is overall MOIC duplicate test"
        save_validated_query(q, "SELECT 1", "test", "")
        msg2 = save_validated_query(q, "SELECT 1", "test", "")
        assert "duplicate" in msg2.lower() or "exists" in msg2.lower() or "skipping" in msg2.lower()

    def test_find_returns_saved_query(self, pg, clean_validated_queries):
        prefix = clean_validated_queries
        question = f"{prefix} total invested capital in portfolio"
        save_validated_query(
            question=question,
            sql_query="SELECT SUM(ABS(investment_value_cr)) FROM portfolio_companies",
            explanation="Sums invested capital.",
            tables_used="portfolio_companies",
        )
        result = json.loads(find_similar_query("invested capital portfolio"))
        assert "matches" in result
        # At least one match should reference the table we saved
        found = any(
            "portfolio_companies" in (m.get("tables_used") or "")
            for m in result["matches"]
        )
        assert found

    def test_find_returns_empty_for_garbage_input(self, pg):
        result = json.loads(find_similar_query("xyzzy flumpf quuux"))
        assert "matches" in result
        assert isinstance(result["matches"], list)

    def test_find_returns_at_most_3_matches(self, pg, clean_validated_queries):
        prefix = clean_validated_queries
        for i in range(5):
            save_validated_query(
                question=f"{prefix} findtest query number {i}",
                sql_query=f"SELECT {i}",
                explanation="test",
                tables_used="portfolio_companies",
            )
        result = json.loads(find_similar_query(f"{prefix} findtest"))
        assert len(result["matches"]) <= 3

    def test_used_count_increments_on_find(self, pg, clean_validated_queries):
        import psycopg2, psycopg2.extras, os
        prefix = clean_validated_queries
        q = f"{prefix} used count increment test"
        save_validated_query(q, "SELECT 1", "test", "portfolio_companies")

        # Call find twice
        find_similar_query(q)
        find_similar_query(q)

        dsn = os.getenv("DATABASE_URL", "postgresql+psycopg://nksquared_user:dev@localhost:5432/nksquared")
        dsn = dsn.replace("postgresql+psycopg://", "postgresql://")
        conn = psycopg2.connect(dsn)
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT used_count FROM nk_validated_queries WHERE question = %s", (q,))
        row = cur.fetchone()
        conn.close()
        assert row is not None
        assert row["used_count"] >= 1
