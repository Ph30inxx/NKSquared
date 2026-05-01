from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User
from app.models.valuation import Valuation
from app.schemas.valuation import ValuationResponse, ValuationUpdate
from app.services import valuation_service

router = APIRouter(prefix="/valuations", tags=["valuations"])

_writer = require_role(["ADMIN", "ANALYST"])


def _get_valuation_or_404(db: Session, valuation_id: int) -> Valuation:
    valuation = db.get(Valuation, valuation_id)
    if valuation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Valuation not found")
    return valuation


@router.patch("/{valuation_id}", response_model=ValuationResponse)
def update_valuation(
    valuation_id: int,
    payload: ValuationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> Valuation:
    valuation = _get_valuation_or_404(db, valuation_id)
    return valuation_service.update_valuation(db, valuation, payload, user_id=user.id)


@router.delete("/{valuation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_valuation(
    valuation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> None:
    valuation = _get_valuation_or_404(db, valuation_id)
    valuation_service.delete_valuation(db, valuation, user_id=user.id)
