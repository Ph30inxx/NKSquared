from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.transaction import PortfolioTransaction
from app.schemas.transaction import (
    NEGATIVE_TYPES,
    POSITIVE_TYPES,
    ZERO_TYPES,
    TransactionCreate,
    TransactionUpdate,
)
from app.services.audit_service import record_audit
from app.services.moic_service import recompute_company_moic

_AUDIT_ENTITY = "portfolio_transaction"
_ZERO = Decimal("0")


def _signed_amount(magnitude: Decimal, transaction_type: str) -> Decimal:
    """Apply § 3.2's sign convention to the user-supplied positive `amount`."""
    if transaction_type in NEGATIVE_TYPES:
        return -magnitude
    if transaction_type in POSITIVE_TYPES:
        return magnitude
    if transaction_type in ZERO_TYPES:
        return _ZERO
    raise ValueError(f"Unknown transaction_type: {transaction_type}")


def _resolve_inr(
    *, amount: Decimal, currency: str, fx_rate_used: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    """
    Returns (amount_inr_cr_magnitude, fx_rate_to_persist).

    INR amounts are 1:1; non-INR needs an explicit fx rate (Sprint 3 will load these
    automatically). When no rate is provided for a non-INR transaction we leave both
    fields NULL — MOIC will skip the row until the rate is supplied.
    """
    if currency.upper() == "INR":
        return amount, Decimal("1")
    if fx_rate_used is None:
        return None, None
    return amount * fx_rate_used, fx_rate_used


def create_transaction(
    db: Session, *, company_id: int, payload: TransactionCreate, user_id: int
) -> PortfolioTransaction:
    magnitude = payload.amount
    signed = _signed_amount(magnitude, payload.transaction_type)
    inr_magnitude, fx_rate = _resolve_inr(
        amount=magnitude, currency=payload.currency, fx_rate_used=payload.fx_rate_used
    )
    amount_inr_cr = (
        None
        if inr_magnitude is None
        else (
            -inr_magnitude
            if payload.transaction_type in NEGATIVE_TYPES
            else (inr_magnitude if payload.transaction_type in POSITIVE_TYPES else _ZERO)
        )
    )

    txn = PortfolioTransaction(
        company_id=company_id,
        transaction_date=payload.transaction_date,
        transaction_type=payload.transaction_type,
        amount_cr=signed,
        original_currency=payload.currency.upper(),
        original_amount=magnitude,
        amount_inr_cr=amount_inr_cr,
        fx_rate_used=fx_rate,
        series=payload.series,
        instrument_type=payload.instrument_type,
        investing_entity=payload.investing_entity,
        shares=payload.shares,
        share_price=payload.share_price,
        pre_money_valuation_cr=payload.pre_money_valuation_cr,
        post_money_valuation_cr=payload.post_money_valuation_cr,
        shareholding_pct=payload.shareholding_pct,
        ssa_reference=payload.ssa_reference,
        ssa_recorded_amount=payload.ssa_recorded_amount,
        notes=payload.notes,
        created_by=user_id,
    )
    db.add(txn)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=txn.id,
        action="CREATE",
        new_value=f"{payload.transaction_type} {magnitude} {payload.currency.upper()}",
    )
    recompute_company_moic(db, company_id)
    db.commit()
    db.refresh(txn)
    return txn


def update_transaction(
    db: Session, txn: PortfolioTransaction, payload: TransactionUpdate, *, user_id: int
) -> PortfolioTransaction:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return txn

    # Track edits for audit before mutation.
    audited_fields: list[tuple[str, object, object]] = []
    for field, new_value in changes.items():
        if field == "amount":
            audited_fields.append(("amount", txn.original_amount, new_value))
        elif field == "currency":
            audited_fields.append(("currency", txn.original_currency, new_value.upper() if new_value else None))
        else:
            audited_fields.append((field, getattr(txn, field), new_value))

    # Apply primitive fields first.
    if "transaction_date" in changes:
        txn.transaction_date = changes["transaction_date"]
    if "series" in changes:
        txn.series = changes["series"]
    if "instrument_type" in changes:
        txn.instrument_type = changes["instrument_type"]
    if "investing_entity" in changes:
        txn.investing_entity = changes["investing_entity"]
    if "shares" in changes:
        txn.shares = changes["shares"]
    if "share_price" in changes:
        txn.share_price = changes["share_price"]
    if "pre_money_valuation_cr" in changes:
        txn.pre_money_valuation_cr = changes["pre_money_valuation_cr"]
    if "post_money_valuation_cr" in changes:
        txn.post_money_valuation_cr = changes["post_money_valuation_cr"]
    if "shareholding_pct" in changes:
        txn.shareholding_pct = changes["shareholding_pct"]
    if "ssa_reference" in changes:
        txn.ssa_reference = changes["ssa_reference"]
    if "ssa_recorded_amount" in changes:
        txn.ssa_recorded_amount = changes["ssa_recorded_amount"]
    if "notes" in changes:
        txn.notes = changes["notes"]

    # Money fields recompute together (sign + INR conversion).
    if any(k in changes for k in ("amount", "transaction_type", "currency", "fx_rate_used")):
        new_type = changes.get("transaction_type", txn.transaction_type)
        new_magnitude = changes.get("amount", txn.original_amount or abs(txn.amount_cr))
        new_currency = (changes.get("currency") or txn.original_currency).upper()
        new_fx = changes.get("fx_rate_used", txn.fx_rate_used)

        txn.transaction_type = new_type
        txn.original_amount = new_magnitude
        txn.original_currency = new_currency
        txn.amount_cr = _signed_amount(new_magnitude, new_type)

        inr_magnitude, fx_rate = _resolve_inr(
            amount=new_magnitude, currency=new_currency, fx_rate_used=new_fx
        )
        if inr_magnitude is None:
            txn.amount_inr_cr = None
            txn.fx_rate_used = None
        else:
            txn.amount_inr_cr = (
                -inr_magnitude
                if new_type in NEGATIVE_TYPES
                else (inr_magnitude if new_type in POSITIVE_TYPES else _ZERO)
            )
            txn.fx_rate_used = fx_rate

    for field, old, new in audited_fields:
        if old == new:
            continue
        record_audit(
            db,
            user_id=user_id,
            entity_type=_AUDIT_ENTITY,
            entity_id=txn.id,
            action="UPDATE",
            field_name=field,
            old_value=old,
            new_value=new,
        )

    db.flush()
    recompute_company_moic(db, txn.company_id)
    db.commit()
    db.refresh(txn)
    return txn


def delete_transaction(db: Session, txn: PortfolioTransaction, *, user_id: int) -> int:
    company_id = txn.company_id
    txn_id = txn.id
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=txn_id,
        action="DELETE",
        old_value=f"{txn.transaction_type} {txn.original_amount} {txn.original_currency}",
    )
    db.delete(txn)
    db.flush()
    recompute_company_moic(db, company_id)
    db.commit()
    return company_id
