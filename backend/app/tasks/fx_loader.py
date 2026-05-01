import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.fx_loader.fetch_daily_rates")
def fetch_daily_rates() -> None:
    """
    Stub for the daily FX loader. Real RBI scraping is deferred — see § 8.3
    `FX_PROVIDER='manual'`. Once a provider is wired up this task should:
      1. Pull yesterday's reference rates for USD/EUR/GBP/JPY (RBI publishes these).
      2. Fall back to a paid feed (xe.com etc.) for AED and other currencies.
      3. Call fx_service.upsert_fx_rate for each.
    """
    logger.info("fetch_daily_rates: TODO — real RBI fetch deferred (manual provider)")
