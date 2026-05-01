from sqlalchemy.orm import Session

from app.models.company import PortfolioCompany
from app.schemas.company import CompanyCreate, CompanyUpdate
from app.services.audit_service import record_audit


_AUDIT_ENTITY = "portfolio_company"


def create_company(db: Session, payload: CompanyCreate, *, user_id: int) -> PortfolioCompany:
    company = PortfolioCompany(**payload.model_dump(exclude_unset=True))
    db.add(company)
    db.flush()  # populate company.id
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=company.id,
        action="CREATE",
        new_value=company.company_name,
    )
    db.commit()
    db.refresh(company)
    return company


def update_company(
    db: Session, company: PortfolioCompany, payload: CompanyUpdate, *, user_id: int
) -> PortfolioCompany:
    changes = payload.model_dump(exclude_unset=True)
    for field, new_value in changes.items():
        old_value = getattr(company, field)
        if old_value == new_value:
            continue
        setattr(company, field, new_value)
        record_audit(
            db,
            user_id=user_id,
            entity_type=_AUDIT_ENTITY,
            entity_id=company.id,
            action="UPDATE",
            field_name=field,
            old_value=old_value,
            new_value=new_value,
        )
    db.commit()
    db.refresh(company)
    return company


def soft_delete_company(db: Session, company: PortfolioCompany, *, user_id: int) -> None:
    if not company.is_active:
        return
    company.is_active = False
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=company.id,
        action="DELETE",
        field_name="is_active",
        old_value=True,
        new_value=False,
    )
    db.commit()
