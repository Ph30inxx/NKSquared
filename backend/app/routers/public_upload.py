from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from itsdangerous import BadSignature, SignatureExpired
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.company import PortfolioCompany
from app.models.mis import MisSubmission
from app.schemas.mis import MisSubmissionCreate, MisSubmissionResponse
from app.services import mis_service
from app.services.upload_token import verify_upload_token

router = APIRouter(prefix="/public", tags=["public"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class TokenPayload(BaseModel):
    company_id: int
    company_name: str
    company_code: str | None
    period_year: int
    period_month: int
    expires_in_days: int


def _decode_token(token: str) -> dict:
    try:
        return verify_upload_token(token)
    except SignatureExpired as exc:
        raise HTTPException(status_code=400, detail="Upload link has expired") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=400, detail="Invalid upload link") from exc


def _resolve_company(db: Session, payload: dict) -> PortfolioCompany:
    company = db.get(PortfolioCompany, int(payload["company_id"]))
    if company is None or not company.is_active:
        raise HTTPException(status_code=400, detail="Company is no longer active")
    return company


@router.get("/upload/verify", response_model=TokenPayload)
def verify(token: str = Query(..., min_length=10), db: Session = Depends(get_db)) -> TokenPayload:
    payload = _decode_token(token)
    company = _resolve_company(db, payload)
    return TokenPayload(
        company_id=company.id,
        company_name=company.display_name or company.company_name,
        company_code=company.company_code,
        period_year=int(payload["year"]),
        period_month=int(payload["month"]),
        expires_in_days=settings.REMINDER_TOKEN_TTL_DAYS,
    )


@router.post("/upload", response_model=MisSubmissionResponse)
async def upload(
    token: str = Query(..., min_length=10),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> MisSubmission:
    payload = _decode_token(token)
    company = _resolve_company(db, payload)
    if not company.company_code:
        raise HTTPException(
            status_code=400,
            detail="Company has no MIS company_code configured; contact your analyst.",
        )
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Only .xlsx files are supported")
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB cap")

    year = int(payload["year"])
    month = int(payload["month"])
    submission = db.execute(
        select(MisSubmission).where(
            MisSubmission.company_id == company.company_code,
            MisSubmission.period_year == year,
            MisSubmission.period_month == month,
        )
    ).scalar_one_or_none()

    if submission is None:
        submission = mis_service.create_submission(
            db,
            MisSubmissionCreate(
                company_id=company.company_code,
                period_year=year,
                period_month=month,
                notes="Uploaded via public reminder link",
            ),
            user_id=None,
        )
    elif submission.status in {"Approved"}:
        raise HTTPException(
            status_code=409,
            detail="This period has already been approved; uploads are closed.",
        )
    else:
        submission.status = "Submitted"
        submission.uploaded_at = datetime.now(timezone.utc)

    return mis_service.attach_file(
        db,
        submission,
        content=content,
        filename=file.filename or "upload.xlsx",
        user_id=None,
    )
