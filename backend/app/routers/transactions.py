from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.transaction import PortfolioTransaction
from app.models.user import User
from app.schemas.transaction import TransactionResponse, TransactionUpdate
from app.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])

_writer = require_role(["ADMIN", "ANALYST"])


def _get_transaction_or_404(db: Session, transaction_id: int) -> PortfolioTransaction:
    txn = db.get(PortfolioTransaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return txn


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> PortfolioTransaction:
    txn = _get_transaction_or_404(db, transaction_id)
    return transaction_service.update_transaction(db, txn, payload, user_id=user.id)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> None:
    txn = _get_transaction_or_404(db, transaction_id)
    transaction_service.delete_transaction(db, txn, user_id=user.id)
