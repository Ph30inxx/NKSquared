from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.models.valuation import Valuation
from app.schemas.valuation import ValuationCreate, ValuationUpdate
from app.services.audit_service import record_audit
from app.services.metrics_service import recompute_company_metrics

_AUDIT_ENTITY = "valuation"


def create_valuation(
    db: Session, *, company_id: int, payload: ValuationCreate, user_id: int | None
) -> Valuation:
    valuation = Valuation(
        company_id=company_id,
        valuation_date=payload.valuation_date,
        post_money_valuation_cr=payload.post_money_valuation_cr,
        pre_money_valuation_cr=payload.pre_money_valuation_cr,
        currency=payload.currency.upper(),
        source=payload.source,
        notes=payload.notes,
        created_by=user_id,
    )
    db.add(valuation)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=valuation.id,
        action="CREATE",
        new_value=f"{payload.post_money_valuation_cr} {payload.currency.upper()} on {payload.valuation_date}",
    )
    db.commit()
    db.refresh(valuation)
    return valuation


def update_valuation(
    db: Session, valuation: Valuation, payload: ValuationUpdate, *, user_id: int | None
) -> Valuation:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return valuation
    for field, new_value in changes.items():
        if field == "currency" and new_value is not None:
            new_value = new_value.upper()
        old_value = getattr(valuation, field)
        if old_value == new_value:
            continue
        setattr(valuation, field, new_value)
        record_audit(
            db,
            user_id=user_id,
            entity_type=_AUDIT_ENTITY,
            entity_id=valuation.id,
            action="UPDATE",
            field_name=field,
            old_value=old_value,
            new_value=new_value,
        )
    db.commit()
    db.refresh(valuation)
    return valuation


def delete_valuation(db: Session, valuation: Valuation, *, user_id: int | None) -> int:
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=valuation.id,
        action="DELETE",
        old_value=f"{valuation.post_money_valuation_cr} on {valuation.valuation_date}",
    )
    db.delete(valuation)
    db.commit()
    return valuation.id


def _latest_shareholding_pct(db: Session, company_id: int) -> Decimal | None:
    """Most recent non-null, non-zero shareholding_pct from this company's transactions."""
    return db.execute(
        select(PortfolioTransaction.shareholding_pct)
        .where(
            PortfolioTransaction.company_id == company_id,
            PortfolioTransaction.shareholding_pct.is_not(None),
            PortfolioTransaction.shareholding_pct != Decimal("0"),
        )
        .order_by(
            PortfolioTransaction.transaction_date.desc(),
            PortfolioTransaction.id.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()


def mark_current(
    db: Session,
    company: PortfolioCompany,
    valuation: Valuation,
    *,
    user_id: int | None,
) -> PortfolioCompany:
    """
    Set company.current_value_cr from a valuation row using NKSquared's pro-rata
    shareholding (most recent non-zero shareholding_pct on a transaction).
    """
    if valuation.company_id != company.id:
        raise ValueError("Valuation does not belong to this company")

    shareholding = _latest_shareholding_pct(db, company.id)
    if shareholding is None:
        raise ValueError(
            "No shareholding_pct recorded on any transaction for this company. "
            "Set it on a transaction before marking a valuation current."
        )

    new_current = (valuation.post_money_valuation_cr or Decimal("0")) * shareholding
    old_current = company.current_value_cr
    company.current_value_cr = new_current

    record_audit(
        db,
        user_id=user_id,
        entity_type="portfolio_company",
        entity_id=company.id,
        action="MARK_CURRENT",
        field_name="current_value_cr",
        old_value=old_current,
        new_value=new_current,
    )
    db.flush()
    recompute_company_metrics(db, company.id)
    db.commit()
    db.refresh(company)
    return company
