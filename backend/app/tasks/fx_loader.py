"""
Live FX loader. Runs every FX_REFRESH_HOURS hours via Celery beat.

For each currency that actually appears in the data (transactions, companies,
mis, valuations), fetch the latest base→currency quote from the configured
provider and upsert XXX→INR for today. Intraday calls overwrite the same-day
row — the `(effective_date, from, to)` unique constraint enforces one row per
pair per day, which is the grain `fx_service.get_fx_rate` already expects.
"""
from __future__ import annotations

import logging
from datetime import date, timezone, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select, union

from app.config import settings
from app.db.session import SessionLocal
from app.models.company import PortfolioCompany
from app.models.mis import MisBuMonthly, MisMonthly
from app.models.transaction import PortfolioTransaction
from app.models.valuation import Valuation
from app.services import fx_provider, fx_service
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

_BASE_INR = "INR"


def _discover_currencies(db) -> list[str]:
    """Distinct non-null, non-INR currencies referenced anywhere in the data."""
    stmt = union(
        select(PortfolioTransaction.original_currency).distinct(),
        select(PortfolioCompany.currency).distinct(),
        select(MisMonthly.currency).distinct(),
        select(MisBuMonthly.currency).distinct(),
        select(Valuation.currency).distinct(),
    )
    raw = db.execute(stmt).scalars().all()
    return sorted({c.upper() for c in raw if c and c.upper() != _BASE_INR})


@celery_app.task(
    name="app.tasks.fx_loader.fetch_daily_rates",
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def fetch_daily_rates(self) -> dict[str, int | str]:
    """
    Pull live FX quotes and upsert XXX→INR for today.

    Returns a small dict for visibility in Celery results / logs. Soft-fails
    when no API key is configured so dev/CI environments don't error.
    """
    if not settings.FX_API_KEY:
        logger.warning("FX_API_KEY is unset; skipping live FX fetch")
        return {"skipped": "no_api_key", "upserted": 0}

    today = datetime.now(timezone.utc).date()
    base = settings.FX_BASE_CURRENCY.upper()

    with SessionLocal() as db:
        currencies = _discover_currencies(db)
        # Always need base→INR to triangulate, even if INR is the only "data" currency.
        targets = sorted({*currencies, _BASE_INR})
        if base in targets:
            targets.remove(base)

        try:
            quotes = fx_provider.fetch_base_quotes(
                api_key=settings.FX_API_KEY,
                base_currency=base,
                currencies=targets,
                provider=settings.FX_PROVIDER,
                timeout_sec=settings.FX_HTTP_TIMEOUT_SEC,
            )
        except fx_provider.FxProviderError as exc:
            logger.error("FX provider rejected request: %s", exc)
            return {"error": str(exc), "upserted": 0}

        base_to_inr = quotes.get(_BASE_INR)
        if base_to_inr is None or base_to_inr <= 0:
            logger.error("FX provider missing %s→INR quote; cannot triangulate", base)
            return {"error": "missing_inr_quote", "upserted": 0}

        upserted = _upsert_inr_rates(
            db,
            base=base,
            quotes=quotes,
            base_to_inr=base_to_inr,
            on_date=today,
            source=settings.FX_PROVIDER,
        )
        db.commit()

    logger.info("FX fetch complete: upserted %d rates for %s", upserted, today.isoformat())
    return {"upserted": upserted, "date": today.isoformat()}


def _upsert_inr_rates(
    db,
    *,
    base: str,
    quotes: dict[str, Decimal],
    base_to_inr: Decimal,
    on_date: date,
    source: str,
) -> int:
    """Triangulate XXX→INR = (base→INR) / (base→XXX) and upsert each pair."""
    count = 0
    for ccy, base_to_ccy in quotes.items():
        # Skip INR→INR; same-currency lookups are handled by fx_service.get_fx_rate.
        if ccy == _BASE_INR:
            continue
        if base_to_ccy is None or base_to_ccy <= 0:
            logger.warning("Skipping %s: invalid quote %r", ccy, base_to_ccy)
            continue
        rate = base_to_inr / base_to_ccy
        # Numeric(12, 6) — keep six decimals to match the column.
        rate = rate.quantize(Decimal("0.000001"))
        fx_service.upsert_fx_rate(
            db,
            from_currency=ccy,
            to_currency=_BASE_INR,
            on_date=on_date,
            rate=rate,
            source=source,
        )
        count += 1
    return count
