from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.services import fx_service


def test_same_currency_short_circuits(db: Session) -> None:
    assert fx_service.get_fx_rate(db, "INR", "INR", date(2024, 1, 1)) == Decimal("1")


def test_exact_date_hit(db: Session) -> None:
    fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 6, 15),
        rate=Decimal("83.50"),
    )
    db.commit()
    assert fx_service.get_fx_rate(db, "USD", "INR", date(2024, 6, 15)) == Decimal("83.50")


def test_falls_back_to_nearest_prior(db: Session) -> None:
    fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 6, 1),
        rate=Decimal("82.00"),
    )
    db.commit()
    # 10 days later, no exact rate; should fall back to 2024-06-01.
    assert fx_service.get_fx_rate(db, "USD", "INR", date(2024, 6, 11)) == Decimal("82.00")


def test_beyond_window_returns_none(db: Session) -> None:
    fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 1, 1),
        rate=Decimal("82.00"),
    )
    db.commit()
    # 60 days later — outside the 30-day fallback window.
    assert fx_service.get_fx_rate(db, "USD", "INR", date(2024, 3, 1)) is None


def test_unknown_pair_returns_none(db: Session) -> None:
    assert fx_service.get_fx_rate(db, "AUD", "INR", date(2024, 6, 1)) is None


def test_upsert_is_idempotent(db: Session) -> None:
    a = fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 6, 1),
        rate=Decimal("83.00"),
        source="seed",
    )
    b = fx_service.upsert_fx_rate(
        db,
        from_currency="USD",
        to_currency="INR",
        on_date=date(2024, 6, 1),
        rate=Decimal("83.50"),
        source="manual",
    )
    db.commit()
    assert a.id == b.id
    assert b.rate == Decimal("83.50")
    assert b.source == "manual"


def test_lookup_uppercases(db: Session) -> None:
    fx_service.upsert_fx_rate(
        db,
        from_currency="usd",
        to_currency="inr",
        on_date=date(2024, 6, 1),
        rate=Decimal("83.00"),
    )
    db.commit()
    assert fx_service.get_fx_rate(db, "usd", "inr", date(2024, 6, 1)) == Decimal("83.00")
