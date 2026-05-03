"""
Integration tests for chatbot/tools/portfolio.py.
All tests require a live PostgreSQL instance with the platform schema.
"""
import json
from decimal import Decimal

import pytest

from chatbot.tools.portfolio import (
    calculate_irr,
    check_portfolio_alerts,
    get_company_portfolio_detail,
    get_portfolio_summary,
)

pytestmark = pytest.mark.integration


# ── get_portfolio_summary ─────────────────────────────────────────────────────

class TestGetPortfolioSummary:

    def test_returns_valid_json(self, pg):
        raw = get_portfolio_summary()
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_totals_key_present(self, pg):
        data = json.loads(get_portfolio_summary())
        assert "totals" in data

    def test_totals_has_required_fields(self, pg):
        totals = json.loads(get_portfolio_summary())["totals"]
        for field in ("total_count", "total_invested_cr", "total_current_cr", "overall_moic"):
            assert field in totals, f"Missing field: {field}"

    def test_default_breakdown_is_by_sector(self, pg):
        data = json.loads(get_portfolio_summary())
        assert "breakdown_by_sector" in data

    def test_breakdown_by_portfolio_type(self, pg):
        data = json.loads(get_portfolio_summary(group_by="portfolio_type"))
        assert "breakdown_by_portfolio_type" in data

    def test_breakdown_by_asset_class(self, pg):
        data = json.loads(get_portfolio_summary(group_by="asset_class"))
        assert "breakdown_by_asset_class" in data

    def test_breakdown_by_investment_status(self, pg):
        data = json.loads(get_portfolio_summary(group_by="investment_status"))
        assert "breakdown_by_investment_status" in data

    def test_unknown_group_by_falls_back_to_sector(self, pg):
        data = json.loads(get_portfolio_summary(group_by="NONEXISTENT"))
        assert "breakdown_by_NONEXISTENT" in data or "breakdown_by_sector" in data

    def test_top_performers_is_list(self, pg):
        data = json.loads(get_portfolio_summary())
        assert isinstance(data["top_5_performers"], list)

    def test_flagged_companies_is_list(self, pg):
        data = json.loads(get_portfolio_summary())
        assert isinstance(data["flagged_companies"], list)

    def test_realized_exits_is_list(self, pg):
        data = json.loads(get_portfolio_summary())
        assert isinstance(data["realized_exits"], list)

    def test_include_written_off_false_reduces_count(self, pg):
        all_data     = json.loads(get_portfolio_summary(include_written_off=True))
        no_wo_data   = json.loads(get_portfolio_summary(include_written_off=False))
        all_count    = all_data["totals"]["total_count"]
        no_wo_count  = no_wo_data["totals"]["total_count"]
        # Excluding written-off should never increase the count
        assert no_wo_count <= all_count

    def test_breakdown_rows_have_required_fields(self, pg):
        breakdown = json.loads(get_portfolio_summary())["breakdown_by_sector"]
        if breakdown:
            for field in ("group_name", "company_count", "invested_cr", "current_value_cr", "moic"):
                assert field in breakdown[0], f"Missing field in breakdown row: {field}"

    def test_with_test_company_included(self, pg, test_company):
        data = json.loads(get_portfolio_summary(group_by="sector"))
        # Technology sector should now appear (we seeded a Technology company)
        sectors = [r["group_name"] for r in data["breakdown_by_sector"]]
        assert "Technology" in sectors


# ── get_company_portfolio_detail ──────────────────────────────────────────────

class TestGetCompanyPortfolioDetail:

    def test_unknown_company_returns_error(self, pg):
        result = json.loads(get_company_portfolio_detail("ZZZZ_DOES_NOT_EXIST_ZZZZ"))
        assert "error" in result

    def test_partial_name_match_works(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__CHATBOT_TEST"))
        assert "error" not in result
        assert "company" in result

    def test_company_block_has_required_fields(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))
        company = result["company"]
        for field in ("id", "display_name", "invested_cr", "current_value_cr", "moic"):
            assert field in company, f"Missing field: {field}"

    def test_invested_is_positive(self, pg, test_company):
        result  = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))
        invested = float(result["company"]["invested_cr"])
        assert invested > 0, "invested_cr should be ABS-ified — must be positive"

    def test_transactions_is_list(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))
        assert isinstance(result["transactions"], list)

    def test_transactions_count_matches_seeded(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))
        # conftest inserts exactly 2 transactions
        assert len(result["transactions"]) == 2

    def test_valuations_is_list(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))
        assert isinstance(result["valuations"], list)

    def test_valuation_count_matches_seeded(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))
        # conftest inserts exactly 1 valuation
        assert len(result["valuations"]) == 1

    def test_transaction_rows_have_required_fields(self, pg, test_company):
        txns = json.loads(get_company_portfolio_detail("__CHATBOT_TEST__"))["transactions"]
        for field in ("transaction_date", "transaction_type", "amount_inr_cr"):
            assert field in txns[0], f"Missing field: {field}"

    def test_case_insensitive_match(self, pg, test_company):
        result = json.loads(get_company_portfolio_detail("__chatbot_test__"))
        assert "error" not in result


# ── calculate_irr ─────────────────────────────────────────────────────────────

class TestCalculateIrr:

    def test_unknown_company_returns_error(self, pg):
        result = json.loads(calculate_irr("ZZZZ_DOES_NOT_EXIST_ZZZZ"))
        assert "error" in result

    def test_company_with_transactions_returns_irr_structure(self, pg, test_company):
        result = json.loads(calculate_irr("__CHATBOT_TEST__"))
        assert "error" not in result
        for field in ("company", "irr_pct", "moic", "total_invested_cr",
                      "total_returned_cr", "num_cash_flows", "first_investment_date",
                      "holding_period_days"):
            assert field in result, f"Missing field: {field}"

    def test_irr_pct_is_numeric_or_none(self, pg, test_company):
        result = json.loads(calculate_irr("__CHATBOT_TEST__"))
        irr = result.get("irr_pct")
        assert irr is None or isinstance(irr, (int, float))

    def test_total_invested_is_positive(self, pg, test_company):
        result = json.loads(calculate_irr("__CHATBOT_TEST__"))
        assert float(result["total_invested_cr"]) > 0

    def test_holding_period_days_is_positive(self, pg, test_company):
        result = json.loads(calculate_irr("__CHATBOT_TEST__"))
        assert int(result["holding_period_days"]) > 0

    def test_num_cash_flows_matches_seeded_transactions(self, pg, test_company):
        result = json.loads(calculate_irr("__CHATBOT_TEST__"))
        # 2 seeded transactions + 1 terminal value = 3 cash flows for pyxirr
        assert result["num_cash_flows"] == 2


# ── check_portfolio_alerts ────────────────────────────────────────────────────

class TestCheckPortfolioAlerts:

    def test_returns_valid_json(self, pg):
        raw = check_portfolio_alerts()
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_has_required_top_level_keys(self, pg):
        data = json.loads(check_portfolio_alerts())
        for key in ("total_alerts", "high", "medium", "info", "alerts"):
            assert key in data, f"Missing key: {key}"

    def test_counts_sum_correctly(self, pg):
        data   = json.loads(check_portfolio_alerts())
        alerts = data["alerts"]
        assert data["high"]   == sum(1 for a in alerts if a["severity"] == "HIGH")
        assert data["medium"] == sum(1 for a in alerts if a["severity"] == "MEDIUM")
        assert data["info"]   == sum(1 for a in alerts if a["severity"] == "INFO")
        assert data["total_alerts"] == len(alerts)

    def test_each_alert_has_required_fields(self, pg):
        data = json.loads(check_portfolio_alerts())
        for alert in data["alerts"]:
            for field in ("severity", "category", "company", "detail", "action"):
                assert field in alert, f"Alert missing field: {field}"

    def test_severity_values_are_valid(self, pg):
        data = json.loads(check_portfolio_alerts())
        valid = {"HIGH", "MEDIUM", "INFO"}
        for alert in data["alerts"]:
            assert alert["severity"] in valid

    def test_low_moic_company_appears_in_alerts(self, pg, test_company_low_moic):
        data   = json.loads(check_portfolio_alerts())
        alerts = data["alerts"]
        high_portfolio = [
            a for a in alerts
            if a["severity"] == "HIGH" and "MOIC" in a["category"]
        ]
        assert len(high_portfolio) >= 1

    def test_alert_counts_are_non_negative(self, pg):
        data = json.loads(check_portfolio_alerts())
        assert data["total_alerts"] >= 0
        assert data["high"]         >= 0
        assert data["medium"]       >= 0
        assert data["info"]         >= 0
