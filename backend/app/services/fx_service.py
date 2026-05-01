from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.forex import ForexRate

# How far back to look for a rate when there's no exact-date match.
_FALLBACK_WINDOW = timedelta(days=30)


def get_fx_rate(
    db: Session,
    from_currency: str,
    to_currency: str,
    on_date: date,
) -> Decimal | None:
    """
    Look up the FX rate for `on_date`. Falls back to the most recent prior date
    within `_FALLBACK_WINDOW`. Returns None if nothing usable is found.

    Same-currency conversions short-circuit to 1.
    """
    src = from_currency.upper()
    dst = to_currency.upper()
    if src == dst:
        return Decimal("1")

    row = db.execute(
        select(ForexRate)
        .where(
            ForexRate.from_currency == src,
            ForexRate.to_currency == dst,
            ForexRate.effective_date <= on_date,
            ForexRate.effective_date >= on_date - _FALLBACK_WINDOW,
        )
        .order_by(ForexRate.effective_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    return row.rate if row is not None else None


def upsert_fx_rate(
    db: Session,
    *,
    from_currency: str,
    to_currency: str,
    on_date: date,
    rate: Decimal,
    source: str | None = None,
) -> ForexRate:
    """Insert or update keyed on (effective_date, from_currency, to_currency). Caller commits."""
    src = from_currency.upper()
    dst = to_currency.upper()
    existing = db.execute(
        select(ForexRate).where(
            ForexRate.from_currency == src,
            ForexRate.to_currency == dst,
            ForexRate.effective_date == on_date,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.rate = rate
        existing.source = source
        db.flush()
        return existing
    row = ForexRate(
        from_currency=src,
        to_currency=dst,
        effective_date=on_date,
        rate=rate,
        source=source,
    )
    db.add(row)
    db.flush()
    return row
