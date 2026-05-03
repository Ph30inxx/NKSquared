from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.mis import MisBuMonthly, MisMonthly, MisOutletMonthly, MisSubmission
from app.models.user import User
from app.schemas.mis import (
    MisSubmissionCreate,
    MisSubmissionListItem,
    MisSubmissionPreview,
    MisSubmissionPreviewRow,
    MisSubmissionRejectRequest,
    MisSubmissionResponse,
    PaginatedMisSubmissions,
)
from app.services import mis_service
from app.services.mis.parser import UnknownTemplateError

router = APIRouter(prefix="/mis", tags=["mis"])

_writer = require_role(["ADMIN", "ANALYST"])

_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB cap


def _get_submission_or_404(db: Session, submission_id: int) -> MisSubmission:
    sub = db.get(MisSubmission, submission_id)
    if sub is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return sub


@router.get("/submissions", response_model=PaginatedMisSubmissions)
def list_submissions(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    status_: str | None = Query(None, alias="status"),
    company_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> PaginatedMisSubmissions:
    base = select(MisSubmission)
    if status_:
        base = base.where(MisSubmission.status == status_)
    if company_id:
        base = base.where(MisSubmission.company_id == company_id)

    total = db.execute(select(func.count()).select_from(base.subquery())).scalar_one()
    items = (
        db.execute(base.order_by(MisSubmission.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return PaginatedMisSubmissions(
        total=total,
        limit=limit,
        offset=offset,
        items=[MisSubmissionListItem.model_validate(s) for s in items],
    )


@router.post(
    "/submissions",
    response_model=MisSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_submission(
    payload: MisSubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> MisSubmission:
    try:
        return mis_service.create_submission(db, payload, user_id=user.id)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"A submission for {payload.company_id} {payload.period_year}-"
                f"{payload.period_month:02d} already exists."
            ),
        ) from exc


@router.get("/submissions/{submission_id}", response_model=MisSubmissionResponse)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> MisSubmission:
    return _get_submission_or_404(db, submission_id)


@router.post("/submissions/{submission_id}/upload", response_model=MisSubmissionResponse)
async def upload_file(
    submission_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> MisSubmission:
    submission = _get_submission_or_404(db, submission_id)
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=415, detail="Only .xlsx files are supported")
    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB cap")
    return mis_service.attach_file(
        db, submission, content=content, filename=file.filename or "upload.xlsx", user_id=user.id
    )


@router.get("/submissions/{submission_id}/preview", response_model=MisSubmissionPreview)
def preview(
    submission_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> MisSubmissionPreview:
    submission = _get_submission_or_404(db, submission_id)
    if submission.source_file_url is None:
        raise HTTPException(status_code=400, detail="Submission has no uploaded file yet")
    try:
        template, parsed = mis_service.preview_submission(submission)
    except UnknownTemplateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    sample = [
        MisSubmissionPreviewRow(
            month_date=r.month_date,
            geography=r.geography,
            revenue_lacs=r.revenue_lacs,
            cogs_lacs=r.cogs_lacs,
            gross_margin_lacs=r.gross_margin_lacs,
            ebitda_lacs=r.ebitda_lacs,
        )
        for r in parsed.monthly_rows[:5]
    ]
    return MisSubmissionPreview(
        template=template,
        monthly_count=len(parsed.monthly_rows),
        bu_count=len(parsed.bu_rows),
        outlet_count=0,
        sample_monthly=sample,
    )


@router.post("/submissions/{submission_id}/approve", response_model=MisSubmissionResponse)
def approve(
    submission_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> MisSubmission:
    submission = _get_submission_or_404(db, submission_id)
    try:
        return mis_service.approve_submission(db, submission, user_id=user.id)
    except UnknownTemplateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/submissions/{submission_id}/reject", response_model=MisSubmissionResponse)
def reject(
    submission_id: int,
    payload: MisSubmissionRejectRequest,
    db: Session = Depends(get_db),
    user: User = Depends(_writer),
) -> MisSubmission:
    submission = _get_submission_or_404(db, submission_id)
    return mis_service.reject_submission(
        db, submission, reason=payload.reason, user_id=user.id
    )
