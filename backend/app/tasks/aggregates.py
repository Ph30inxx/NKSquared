"""Refresh `portfolio_aggregates_mv`. The view powers /portfolio/summary,
/portfolio/by-sector, and /portfolio/by-category — keeping it ~5 min fresh
trades a few minutes of staleness for one-pass reads on 500+ companies."""
import logging

from sqlalchemy import text

from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def schedule_refresh() -> None:
    """Best-effort enqueue of `refresh_portfolio_aggregates`. Tolerates broker
    being unavailable (local dev without Redis/Celery), so production write
    paths can fan-out without becoming dependent on the scheduler."""
    try:
        refresh_portfolio_aggregates.delay()
    except Exception as exc:
        logger.debug("could not enqueue MV refresh: %s", exc)


@celery_app.task(name="app.tasks.aggregates.refresh_portfolio_aggregates")
def refresh_portfolio_aggregates() -> str:
    """REFRESH the materialized view. Uses CONCURRENTLY when possible so reads
    aren't blocked; falls back to a plain refresh if no unique index exists."""
    db = SessionLocal()
    try:
        try:
            db.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY portfolio_aggregates_mv")
            )
            db.commit()
            return "refreshed_concurrently"
        except Exception as exc:
            db.rollback()
            logger.warning(
                "concurrent refresh failed, falling back to blocking: %s", exc
            )
            db.execute(text("REFRESH MATERIALIZED VIEW portfolio_aggregates_mv"))
            db.commit()
            return "refreshed_blocking"
    finally:
        db.close()
