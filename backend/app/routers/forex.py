from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.forex import ForexRate
from app.models.user import User
from app.schemas.forex import ForexRateBulkCreate, ForexRateCreate, ForexRateResponse
from app.services import fx_service

router = APIRouter(prefix="/forex-rates", tags=["forex"])


@router.get("", response_model=list[ForexRateResponse])
def list_rates(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    from_currency: str | None = Query(None, alias="from"),
    to_currency: str | None = Query(None, alias="to"),
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(200, ge=1, le=1000),
) -> list[ForexRate]:
    stmt = select(ForexRate)
    if from_currency:
        stmt = stmt.where(ForexRate.from_currency == from_currency.upper())
    if to_currency:
        stmt = stmt.where(ForexRate.to_currency == to_currency.upper())
    if from_date:
        stmt = stmt.where(ForexRate.effective_date >= from_date)
    if to_date:
        stmt = stmt.where(ForexRate.effective_date <= to_date)
    stmt = stmt.order_by(ForexRate.effective_date.desc(), ForexRate.from_currency).limit(limit)
    return list(db.execute(stmt).scalars().all())


@router.post("", response_model=ForexRateResponse, status_code=status.HTTP_201_CREATED)
def upsert_rate(
    payload: ForexRateCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ForexRate:
    row = fx_service.upsert_fx_rate(
        db,
        from_currency=payload.from_currency,
        to_currency=payload.to_currency,
        on_date=payload.effective_date,
        rate=payload.rate,
        source=payload.source,
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/bulk", response_model=list[ForexRateResponse], status_code=status.HTTP_201_CREATED)
def bulk_upsert(
    payload: ForexRateBulkCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> list[ForexRate]:
    rows = [
        fx_service.upsert_fx_rate(
            db,
            from_currency=r.from_currency,
            to_currency=r.to_currency,
            on_date=r.effective_date,
            rate=r.rate,
            source=r.source,
        )
        for r in payload.rates
    ]
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows
