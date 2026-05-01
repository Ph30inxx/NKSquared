from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.company import PortfolioCompany
from app.models.transaction import PortfolioTransaction
from app.models.user import User
from app.schemas.company import (
    CompanyCreate,
    CompanyListItem,
    CompanyResponse,
    CompanyUpdate,
    PaginatedCompanies,
)
from app.schemas.transaction import TransactionCreate, TransactionResponse
from app.services import company_service, transaction_service

router = APIRouter(prefix="/companies", tags=["companies"])

_writer = require_role(["ADMIN", "ANALYST"])


@router.get("", response_model=PaginatedCompanies)
def list_companies(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sector: str | None = None,
    investment_status: str | None = None,
    portfolio_type: str | None = None,
    q: str | None = Query(None, description="Search company_name or display_name (ILIKE)"),
    include_inactive: bool = False,
) -> PaginatedCompanies:
    base = select(PortfolioCompany)
    if not include_inactive:
        base = base.where(PortfolioCompany.is_active.is_(True))
    if sector:
        base = base.where(PortfolioCompany.sector == sector)
    if investment_status:
        base = base.where(PortfolioCompany.investment_status == investment_status)
    if portfolio_type:
        base = base.where(PortfolioCompany.portfolio_type == portfolio_type)
    if q:
        like = f"%{q}%"
        base = base.where(
            or_(
                PortfolioCompany.company_name.ilike(like),
                PortfolioCompany.display_name.ilike(like),
            )
        )

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(
            base.order_by(PortfolioCompany.company_name).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return PaginatedCompanies(
        total=total,
        limit=limit,
        offset=offset,
        items=[CompanyListItem.model_validate(c) for c in items],
    )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> PortfolioCompany:
    return company_service.create_company(db, payload, user_id=user.id)


def _get_company_or_404(db: Session, company_id: int) -> PortfolioCompany:
    company = db.get(PortfolioCompany, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PortfolioCompany:
    return _get_company_or_404(db, company_id)


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> PortfolioCompany:
    company = _get_company_or_404(db, company_id)
    return company_service.update_company(db, company, payload, user_id=user.id)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def soft_delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> None:
    company = _get_company_or_404(db, company_id)
    company_service.soft_delete_company(db, company, user_id=user.id)


@router.get("/{company_id}/transactions", response_model=list[TransactionResponse])
def list_company_transactions(
    company_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[PortfolioTransaction]:
    _get_company_or_404(db, company_id)
    return list(
        db.execute(
            select(PortfolioTransaction)
            .where(PortfolioTransaction.company_id == company_id)
            .order_by(PortfolioTransaction.transaction_date, PortfolioTransaction.id)
        )
        .scalars()
        .all()
    )


@router.post(
    "/{company_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_company_transaction(
    company_id: int,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> PortfolioTransaction:
    _get_company_or_404(db, company_id)
    return transaction_service.create_transaction(
        db, company_id=company_id, payload=payload, user_id=user.id
    )
