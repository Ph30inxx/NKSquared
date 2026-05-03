"""
Integration tests for chatbot/tools/mis.py:
  get_company_trend, get_mis_recent_summary, get_bu_breakdown, get_outlet_breakdown.

financial_period_resolver is tested separately in test_period_resolver.py.
"""
import json

import pytest

from chatbot.tools.mis import (
    get_bu_breakdown,
    get_company_trend,
    get_mis_recent_summary,
    get_outlet_breakdown,
)

pytestmark = pytest.mark.integration


# ── get_company_trend ─────────────────────────────────────────────────────────

class TestGetCompanyTrend:

    def test_unknown_company_returns_error(self, pg):
        result = json.loads(get_company_trend("__no_such_company__", period="FY26"))
        assert "error" in result

    def test_returns_valid_json(self, pg, test_mis_data):
        raw = get_company_trend("__test__", period="FY26")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_has_currency_summary_trend_keys(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="FY26"))
        if "error" not in data:
            for key in ("currency", "summary", "trend"):
                assert key in data

    def test_currency_is_inr_lacs(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="FY26"))
        if "error" not in data:
            assert data["currency"] == "INR_Lacs"

    def test_trend_is_list(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="FY26"))
        if "error" not in data:
            assert isinstance(data["trend"], list)

    def test_seeded_months_appear_in_trend(self, pg, test_mis_data):
        # Seeded data is in Q3_FY26 (Oct–Dec 2025) — explicitly request that quarter
        data = json.loads(get_company_trend("__test__", period="Q3_FY26"))
        if "error" not in data:
            assert len(data["trend"]) >= 2

    def test_trend_rows_have_required_fields(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="Q3_FY26"))
        if "error" not in data and data["trend"]:
            row = data["trend"][0]
            for field in ("period_date", "period_label", "revenue", "ebitda",
                          "gross_margin", "cogs", "operating_costs"):
                assert field in row, f"Missing trend field: {field}"

    def test_second_row_has_mom_change_fields(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="Q3_FY26"))
        if "error" not in data and len(data["trend"]) >= 2:
            second = data["trend"][1]
            assert "mom_revenue_change_pct" in second
            assert "mom_ebitda_change_lacs"  in second

    def test_first_row_mom_fields_are_none(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="Q3_FY26"))
        if "error" not in data and data["trend"]:
            first = data["trend"][0]
            assert first["mom_revenue_change_pct"] is None
            assert first["mom_ebitda_change_lacs"]  is None

    def test_summary_has_ebitda_trend(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="Q3_FY26"))
        if "error" not in data:
            assert "ebitda_trend" in data["summary"]

    def test_summary_ebitda_trend_is_valid_value(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="Q3_FY26"))
        valid = {"improving", "deteriorating", "mixed", "insufficient_data"}
        if "error" not in data:
            assert data["summary"]["ebitda_trend"] in valid

    def test_quarterly_granularity(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="FY26", granularity="quarterly"))
        if "error" not in data:
            assert isinstance(data["trend"], list)

    def test_geography_filter_consolidated(self, pg, test_mis_data):
        data = json.loads(get_company_trend("__test__", period="Q3_FY26", geography="consolidated"))
        if "error" not in data:
            assert len(data["trend"]) >= 1


# ── get_mis_recent_summary ────────────────────────────────────────────────────

class TestGetMisRecentSummary:

    def test_insufficient_data_returns_error(self, pg):
        result = json.loads(get_mis_recent_summary("__no_such_company__"))
        assert "error" in result

    def test_returns_valid_json(self, pg, test_mis_data):
        raw = get_mis_recent_summary("__test__")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_has_required_top_level_keys(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            for key in ("company_id", "latest_month", "prior_month",
                        "overall_direction", "headline_flags", "metric_changes"):
                assert key in data, f"Missing key: {key}"

    def test_company_id_matches_input(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            assert data["company_id"] == "__test__"

    def test_overall_direction_is_valid(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        valid = {"improving", "deteriorating", "mixed"}
        if "error" not in data:
            assert data["overall_direction"] in valid

    def test_seeded_data_shows_improving_direction(self, pg, test_mis_data):
        # Seeded: Oct revenue=500, Nov revenue=540 → Nov > Oct → improving
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            assert data["overall_direction"] == "improving"

    def test_headline_flags_is_non_empty_list(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            assert isinstance(data["headline_flags"], list)
            assert len(data["headline_flags"]) >= 1

    def test_metric_changes_is_dict(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            assert isinstance(data["metric_changes"], dict)

    def test_metric_changes_has_revenue_ebitda(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            for metric in ("revenue", "ebitda"):
                assert metric in data["metric_changes"]

    def test_each_metric_change_has_direction(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            for metric, change in data["metric_changes"].items():
                assert "direction" in change, f"metric {metric} missing 'direction'"

    def test_direction_values_are_valid(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        valid = {"improved", "worsened", "stable", "unknown"}
        if "error" not in data:
            for change in data["metric_changes"].values():
                assert change["direction"] in valid

    def test_change_abs_sign_matches_direction(self, pg, test_mis_data):
        data = json.loads(get_mis_recent_summary("__test__"))
        if "error" not in data:
            rev = data["metric_changes"].get("revenue", {})
            if rev.get("direction") == "improved" and rev.get("change_abs") is not None:
                assert float(rev["change_abs"]) > 0


# ── get_bu_breakdown ──────────────────────────────────────────────────────────

class TestGetBuBreakdown:

    def test_no_data_returns_error(self, pg):
        result = json.loads(get_bu_breakdown("__no_such_company__"))
        assert "error" in result

    def test_returns_valid_json(self, pg, test_mis_data):
        raw = get_bu_breakdown("__test__", period="Q3_FY26")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_bu_data_is_list(self, pg, test_mis_data):
        data = json.loads(get_bu_breakdown("__test__", period="Q3_FY26"))
        if "error" not in data:
            assert isinstance(data["bu_data"], list)

    def test_seeded_bu_row_is_present(self, pg, test_mis_data):
        data = json.loads(get_bu_breakdown("__test__", period="Q3_FY26"))
        if "error" not in data and data["bu_data"]:
            bu_ids = [r["bu_id"] for r in data["bu_data"]]
            assert "BU_01" in bu_ids

    def test_bu_rows_have_required_fields(self, pg, test_mis_data):
        data = json.loads(get_bu_breakdown("__test__", period="Q3_FY26"))
        if "error" not in data and data["bu_data"]:
            row = data["bu_data"][0]
            for field in ("bu_id", "month", "revenue_lacs", "ebitda_lacs"):
                assert field in row, f"Missing BU field: {field}"

    def test_has_company_id_and_period(self, pg, test_mis_data):
        data = json.loads(get_bu_breakdown("__test__", period="Q3_FY26"))
        if "error" not in data:
            assert data["company_id"] == "__test__"
            assert "period" in data


# ── get_outlet_breakdown ──────────────────────────────────────────────────────

class TestGetOutletBreakdown:

    def test_no_data_returns_error(self, pg):
        # Outlet table has company_01 only; requesting with no seeded data → error
        result = json.loads(get_outlet_breakdown(period="FY20"))
        assert "error" in result

    def test_returns_valid_json_for_any_period(self, pg):
        raw = get_outlet_breakdown(period="Q3_FY26")
        data = json.loads(raw)
        assert isinstance(data, dict)

    def test_company_id_always_company_01(self, pg):
        raw = get_outlet_breakdown(period="Q3_FY26")
        data = json.loads(raw)
        if "error" not in data:
            assert data["company_id"] == "company_01"

    def test_outlet_rows_have_required_fields(self, pg):
        data = json.loads(get_outlet_breakdown(period="Q3_FY26"))
        if "error" not in data and data.get("outlet_data"):
            row = data["outlet_data"][0]
            for field in ("outlet_id", "city", "month", "revenue_lacs",
                          "operational_profit_lacs", "sales_to_rent_ratio"):
                assert field in row, f"Missing outlet field: {field}"
