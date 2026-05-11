"""Tests for the live FX loader task."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.forex import ForexRate
from app.models.transaction import PortfolioTransaction
from app.services import fx_provider
from app.tasks import fx_loader


def _seed_company(db: Session, *, currency: str) -> PortfolioCompany:
    c = PortfolioCompany(
        company_name=f"Co-{currency}",
        currency=currency,
        reporting_frequency="Monthly",
        is_active=True,
    )
    db.add(c)
    db.flush()
    return c


def _seed_txn(db: Session, *, company_id: int, currency: str) -> None:
    db.add(
        PortfolioTransaction(
            company_id=company_id,
            transaction_date=date(2024, 1, 1),
            transaction_type="Investment",
            amount_cr=Decimal("1"),
            original_currency=currency,
        )
    )
    db.flush()


def test_discover_currencies_uniques_and_excludes_inr(db: Session) -> None:
    inr_co = _seed_company(db, currency="INR")
    usd_co = _seed_company(db, currency="USD")
    _seed_txn(db, company_id=inr_co.id, currency="EUR")
    _seed_txn(db, company_id=usd_co.id, currency="USD")  # duplicate of company currency
    _seed_txn(db, company_id=usd_co.id, currency="aud")  # case-insensitive
    db.commit()

    found = fx_loader._discover_currencies(db)
    assert found == ["AUD", "EUR", "USD"]


def test_upsert_inr_rates_triangulates_via_base(db: Session) -> None:
    """USD→INR=83, USD→EUR=0.92  ⇒  EUR→INR ≈ 90.217391"""
    quotes = {
        "INR": Decimal("83.00"),
        "EUR": Decimal("0.92"),
        "USD": Decimal("1"),
    }
    count = fx_loader._upsert_inr_rates(
        db,
        base="USD",
        quotes=quotes,
        base_to_inr=quotes["INR"],
        on_date=date(2024, 6, 1),
        source="currencylayer",
    )
    db.commit()
    # INR is skipped (same-currency); EUR and USD are upserted.
    assert count == 2

    rows = {r.from_currency: r for r in db.query(ForexRate).all()}
    assert set(rows) == {"EUR", "USD"}
    assert rows["USD"].rate == Decimal("83.000000")  # USD→INR direct
    # 83 / 0.92 = 90.21739130... → quantized to 6dp
    assert rows["EUR"].rate == Decimal("90.217391")
    assert all(r.source == "currencylayer" for r in rows.values())
    assert all(r.to_currency == "INR" for r in rows.values())


def test_upsert_skips_invalid_quotes(db: Session) -> None:
    quotes = {
        "INR": Decimal("83"),
        "GBP": Decimal("0"),  # invalid
        "JPY": Decimal("150"),
    }
    count = fx_loader._upsert_inr_rates(
        db,
        base="USD",
        quotes=quotes,
        base_to_inr=quotes["INR"],
        on_date=date(2024, 6, 1),
        source="currencylayer",
    )
    db.commit()
    # INR skipped (same-currency), GBP skipped (zero rate), JPY upserted.
    assert count == 1
    found = {r.from_currency for r in db.query(ForexRate).all()}
    assert found == {"JPY"}


def test_fetch_daily_rates_skips_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fx_loader.settings, "FX_API_KEY", None)
    # Force any accidental HTTP call to fail loudly so the test can't pass by accident.
    monkeypatch.setattr(
        fx_provider,
        "fetch_base_quotes",
        lambda **_: pytest.fail("provider should not be called when key is missing"),
    )
    result = fx_loader.fetch_daily_rates.run()
    assert result == {"skipped": "no_api_key", "upserted": 0}


def _capture_request(monkeypatch: pytest.MonkeyPatch, body: dict) -> dict:
    """Stub httpx.get; capture the call and return `body` as JSON."""
    captured: dict = {}

    class _Resp:
        def json(self) -> dict:
            return body

        def raise_for_status(self) -> None:
            return None

    def _fake_get(url: str, params: dict, timeout: int) -> _Resp:  # type: ignore[override]
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return _Resp()

    import app.services.fx_provider as mod

    monkeypatch.setattr(mod.httpx, "get", _fake_get)
    return captured


def test_fixer_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_request(
        monkeypatch,
        {"success": True, "base": "EUR", "rates": {"USD": 1.08, "INR": 90.5}},
    )
    quotes = fx_provider.fetch_base_quotes(
        api_key="K",
        base_currency="EUR",
        currencies=["USD", "INR"],
        provider="fixer",
    )
    assert "data.fixer.io" in captured["url"]
    assert "symbols" in captured["params"]
    assert captured["params"]["symbols"] == "INR,USD"
    assert "source" not in captured["params"]
    assert "base" not in captured["params"]
    assert quotes["USD"] == Decimal("1.08")
    assert quotes["INR"] == Decimal("90.5")
    assert quotes["EUR"] == Decimal("1")  # base always included


def test_currencylayer_request_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _capture_request(
        monkeypatch,
        {"success": True, "source": "USD", "quotes": {"USDINR": 83.0, "USDEUR": 0.92}},
    )
    quotes = fx_provider.fetch_base_quotes(
        api_key="K",
        base_currency="USD",
        currencies=["INR", "EUR"],
        provider="currencylayer",
    )
    assert "api.currencylayer.com" in captured["url"]
    assert captured["params"]["currencies"] == "EUR,INR"
    assert captured["params"]["source"] == "USD"
    assert "symbols" not in captured["params"]
    assert quotes["INR"] == Decimal("83.0")
    assert quotes["EUR"] == Decimal("0.92")


def test_provider_error_surfaces_structured_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _capture_request(
        monkeypatch,
        {"success": False, "error": {"code": 105, "type": "base_currency_access_restricted"}},
    )
    with pytest.raises(fx_provider.FxProviderError, match="105"):
        fx_provider.fetch_base_quotes(
            api_key="K",
            base_currency="USD",
            currencies=["INR"],
            provider="fixer",
        )

