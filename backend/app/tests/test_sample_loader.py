from pathlib import Path

import pytest

from app.services.sample_loader.mappings import (
    normalize_asset_class,
    normalize_investment_status,
    normalize_portfolio_status,
    normalize_portfolio_type,
)
from app.services.sample_loader.portfolio_loader import load_portfolio

# The container mounts ./samples:/samples — the test runs in that environment.
SAMPLES = Path("/samples/Copy of Portolfio_Base_Structure.xlsm")


def test_normalize_portfolio_type() -> None:
    assert normalize_portfolio_type("Entity_D Core") == "Entity_D_Core"
    assert normalize_portfolio_type("Entity_D Non-Core") == "Entity_D_Non_Core"
    assert normalize_portfolio_type("Entity_C Orig.") == "Entity_C"
    assert normalize_portfolio_type("Strategic Equity") == "Strategic_Equity"
    assert normalize_portfolio_type("Real Estate Debt") == "Real_Estate_Debt"
    assert normalize_portfolio_type("Unknown") is None
    assert normalize_portfolio_type(None) is None


def test_normalize_investment_status_handles_trailing_space() -> None:
    assert normalize_investment_status("Active") == "Active"
    assert normalize_investment_status("Exit via IPO route ") == "Exit_via_IPO"
    assert normalize_investment_status("Matured") == "Matured"
    assert normalize_investment_status("Written off") == "Written_off"
    assert normalize_investment_status(None) is None


def test_normalize_asset_class() -> None:
    assert normalize_asset_class("Direct Equity") == "Direct_Equity"
    assert normalize_asset_class("Fund Investment") == "Fund_Investment"
    assert normalize_asset_class("Debt Instrument") == "Debt_Instrument"


def test_normalize_portfolio_status_handles_uk_spelling() -> None:
    assert normalize_portfolio_status("Unrealized") == "Unrealized"
    assert normalize_portfolio_status("Unrealised") == "Unrealized"
    assert normalize_portfolio_status("Realized") == "Realized"


@pytest.mark.skipif(not SAMPLES.exists(), reason="samples not mounted")
def test_load_portfolio_extracts_known_companies() -> None:
    parsed = load_portfolio(SAMPLES)
    by_name = {p.company_name: p for p in parsed}

    assert "Company_01_Display" in by_name, "first row of Portfolio Master"
    assert "Company_02" in by_name
    assert "Company_60" in by_name, "realised IPO row"
    assert "Company_53 Life LLP" in by_name, "duplicate-T1 tranche edge case"
    assert "Company_29D" in by_name, "no-detail-sheet edge case"

    # Section dividers / aggregation rows must NOT appear as companies.
    for sentinel in {"Realised Portfolio", "Unrealised Portfolio", "Entity_D Core", "Strategic Equity"}:
        assert sentinel not in by_name, f"sentinel {sentinel!r} leaked into parsed companies"

    # Realised company status mapped correctly (trailing space scrubbed).
    assert by_name["Company_60"].investment_status == "Exit_via_IPO"

    # Company_29D has no detail sheet so 0 transactions.
    company_29d = by_name["Company_29D"]
    assert company_29d.has_detail_sheet is False
    assert company_29d.transactions == []
    # Portfolio Master sets a current value > 0 even without a detail sheet.
    assert company_29d.current_value_cr is not None

    # Company_53 Life LLP has 3 tranches despite duplicate "T1" labels.
    company_53 = by_name["Company_53 Life LLP"]
    assert company_53.has_detail_sheet is True
    assert len(company_53.transactions) == 3

    # First transaction by date is Investment, others are Follow_on.
    for parsed_company in [by_name["Company_02"], by_name["Company_04"], company_53]:
        if not parsed_company.transactions:
            continue
        assert parsed_company.transactions[0].transaction_type == "Investment"
        for t in parsed_company.transactions[1:]:
            assert t.transaction_type == "Follow_on"
