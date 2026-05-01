from sqlalchemy.orm import Session

from app.services.moic_service import MoicResult, recompute_company_moic
from app.services.xirr_service import recompute_company_xirr


def recompute_company_metrics(db: Session, company_id: int) -> MoicResult:
    """Refresh MOIC and IRR for a single company. Caller commits."""
    moic = recompute_company_moic(db, company_id)
    recompute_company_xirr(db, company_id)
    return moic
