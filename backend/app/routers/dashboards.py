from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardOverview,
    PortfolioBucket,
    PortfolioSummary,
)
from app.services import portfolio_service

router = APIRouter(tags=["dashboards"])


@router.get("/dashboards/portfolio-overview", response_model=DashboardOverview)
def portfolio_overview(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return portfolio_service.dashboard_overview(db)


@router.get("/portfolio/summary", response_model=PortfolioSummary)
def portfolio_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    return portfolio_service.summary(db)


@router.get("/portfolio/by-sector", response_model=list[PortfolioBucket])
def portfolio_by_sector(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    return [b.__dict__ for b in portfolio_service.by_sector(db)]


@router.get("/portfolio/by-vintage", response_model=list[PortfolioBucket])
def portfolio_by_vintage(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    return [b.__dict__ for b in portfolio_service.by_vintage(db)]


@router.get("/portfolio/by-category", response_model=list[PortfolioBucket])
def portfolio_by_category(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict]:
    return [b.__dict__ for b in portfolio_service.by_category(db)]
