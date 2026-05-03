import logging
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.mis import (
    MisAnomaly,
    MisBuMonthly,
    MisMonthly,
    MisOutletMonthly,
    MisSubmission,
)
from app.schemas.mis import MisSubmissionCreate
from app.services import anomaly_detector
from app.services.audit_service import record_audit
from app.services.mis import parser, storage
from app.services.sample_loader.mis_loader_v1 import ParsedMisSubmission

logger = logging.getLogger(__name__)

_AUDIT_ENTITY = "mis_submission"


def _derive_fiscal_year(period_year: int, period_month: int) -> str:
    """Indian FY: April → March. April 2025 = FY26."""
    fy_end = period_year + (1 if period_month >= 4 else 0)
    return f"FY{str(fy_end)[-2:]}"


def create_submission(
    db: Session, payload: MisSubmissionCreate, *, user_id: int | None
) -> MisSubmission:
    fiscal_year = payload.fiscal_year or _derive_fiscal_year(
        payload.period_year, payload.period_month
    )
    sub = MisSubmission(
        company_id=payload.company_id,
        period_year=payload.period_year,
        period_month=payload.period_month,
        fiscal_year=fiscal_year,
        status="Pending",
        notes=payload.notes,
    )
    db.add(sub)
    db.flush()
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=sub.id,
        action="CREATE",
        new_value=f"{payload.company_id} {payload.period_year}-{payload.period_month:02d}",
    )
    db.commit()
    db.refresh(sub)
    return sub


def attach_file(
    db: Session,
    submission: MisSubmission,
    *,
    content: bytes,
    filename: str,
    user_id: int | None,
) -> MisSubmission:
    path = storage.save_uploaded_file(submission.id, content)
    submission.source_file_name = filename
    submission.source_file_url = str(path)
    submission.uploaded_at = datetime.now(timezone.utc)
    submission.uploaded_by = user_id
    if submission.status == "Pending":
        submission.status = "Submitted"
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=submission.id,
        action="UPLOAD",
        field_name="source_file_name",
        new_value=filename,
    )
    db.flush()
    _refresh_anomalies(db, submission)
    db.commit()
    db.refresh(submission)
    return submission


def preview_submission(submission: MisSubmission) -> tuple[str, ParsedMisSubmission]:
    """Re-parse the file on disk; commit nothing. Raises UnknownTemplateError on bad file."""
    if submission.source_file_url is None:
        raise ValueError("Submission has no uploaded file")
    template, parsed = parser.parse(
        storage.upload_path(submission.id), company_id=submission.company_id
    )
    return template, parsed


def _bu_kwargs(row, submission_id: int) -> dict:
    cols = {c.name for c in MisBuMonthly.__table__.columns}
    data = {f.name: getattr(row, f.name) for f in dataclass_fields(row)}
    data["submission_id"] = submission_id
    return {k: v for k, v in data.items() if k in cols}


def _monthly_kwargs(row, submission_id: int) -> dict:
    cols = {c.name for c in MisMonthly.__table__.columns}
    data = {f.name: getattr(row, f.name) for f in dataclass_fields(row)}
    data["submission_id"] = submission_id
    return {k: v for k, v in data.items() if k in cols}


def approve_submission(
    db: Session, submission: MisSubmission, *, user_id: int | None
) -> MisSubmission:
    if submission.source_file_url is None:
        raise ValueError("Cannot approve a submission with no uploaded file")
    template, parsed = preview_submission(submission)

    # Idempotent: re-approving wipes old children + re-inserts.
    db.execute(delete(MisOutletMonthly).where(MisOutletMonthly.submission_id == submission.id))
    db.execute(delete(MisBuMonthly).where(MisBuMonthly.submission_id == submission.id))
    db.execute(delete(MisMonthly).where(MisMonthly.submission_id == submission.id))

    for r in parsed.monthly_rows:
        db.add(MisMonthly(**_monthly_kwargs(r, submission.id)))
    for r in parsed.bu_rows:
        db.add(MisBuMonthly(**_bu_kwargs(r, submission.id)))

    submission.status = "Approved"
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.reviewed_by = user_id
    submission.rejection_reason = None
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=submission.id,
        action="APPROVE",
        new_value=f"template={template} monthly={len(parsed.monthly_rows)} bu={len(parsed.bu_rows)}",
    )
    db.flush()
    _refresh_anomalies(db, submission, parsed=parsed)
    db.commit()
    db.refresh(submission)
    return submission


def _refresh_anomalies(
    db: Session,
    submission: MisSubmission,
    *,
    parsed: ParsedMisSubmission | None = None,
) -> None:
    """Re-run the detector and replace persisted anomalies. Tolerant of parse
    failures (logged + skipped) so detection never blocks the upload/approval flow.
    """
    if parsed is None:
        if submission.source_file_url is None:
            return
        try:
            _, parsed = preview_submission(submission)
        except Exception as exc:  # parser.UnknownTemplateError or anything else
            logger.warning(
                "anomaly detector skipped for submission %s: %s", submission.id, exc
            )
            db.execute(delete(MisAnomaly).where(MisAnomaly.submission_id == submission.id))
            submission.anomaly_count = 0
            return

    findings = anomaly_detector.detect(db, submission, parsed)
    db.execute(delete(MisAnomaly).where(MisAnomaly.submission_id == submission.id))
    for f in findings:
        db.add(
            MisAnomaly(
                submission_id=submission.id,
                rule_code=f.rule_code,
                severity=f.severity,
                message=f.message,
                metric=f.metric,
                period_year=f.period_year,
                period_month=f.period_month,
                geography=f.geography,
                bu_id=f.bu_id,
            )
        )
    submission.anomaly_count = len(findings)


def reject_submission(
    db: Session, submission: MisSubmission, *, reason: str, user_id: int | None
) -> MisSubmission:
    submission.status = "Rejected"
    submission.rejection_reason = reason
    submission.reviewed_at = datetime.now(timezone.utc)
    submission.reviewed_by = user_id
    record_audit(
        db,
        user_id=user_id,
        entity_type=_AUDIT_ENTITY,
        entity_id=submission.id,
        action="REJECT",
        new_value=reason,
    )
    db.commit()
    db.refresh(submission)
    return submission
