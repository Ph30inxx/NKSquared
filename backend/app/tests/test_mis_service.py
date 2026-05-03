import io
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.mis import MisBuMonthly, MisMonthly, MisSubmission
from app.schemas.mis import MisSubmissionCreate
from app.services import mis_service
from app.services.mis import parser, storage

SAMPLES = Path("/samples")
COMPANY_01_FILE = SAMPLES / "Company_01_Mock MIS_FY26.xlsx"
COMPANY_02_FILE = SAMPLES / "Company_02_Mock MIS_FY26.xlsx"


def _make_empty_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "no MIS data here"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_create_submission_enforces_unique_period(db: Session) -> None:
    payload = MisSubmissionCreate(
        company_id="company_99", period_year=2025, period_month=4
    )
    mis_service.create_submission(db, payload, user_id=None)
    with pytest.raises(IntegrityError):
        mis_service.create_submission(db, payload, user_id=None)


def test_attach_file_advances_status_to_submitted(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_a", period_year=2025, period_month=5),
        user_id=None,
    )
    sub = mis_service.attach_file(
        db, sub, content=b"fake xlsx bytes", filename="test.xlsx", user_id=None
    )
    assert sub.status == "Submitted"
    assert sub.source_file_name == "test.xlsx"
    assert sub.uploaded_at is not None
    saved = (tmp_path / f"{sub.id}.xlsx").read_bytes()
    assert saved == b"fake xlsx bytes"


@pytest.mark.skipif(not COMPANY_01_FILE.exists(), reason="samples not mounted")
def test_preview_v1_template(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_01", period_year=2026, period_month=3),
        user_id=None,
    )
    mis_service.attach_file(
        db,
        sub,
        content=COMPANY_01_FILE.read_bytes(),
        filename=COMPANY_01_FILE.name,
        user_id=None,
    )
    template, parsed = mis_service.preview_submission(sub)
    assert template == "v1"
    assert len(parsed.monthly_rows) > 0
    assert len(parsed.bu_rows) > 0


@pytest.mark.skipif(not COMPANY_02_FILE.exists(), reason="samples not mounted")
def test_preview_v2_template(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_02", period_year=2026, period_month=3),
        user_id=None,
    )
    mis_service.attach_file(
        db,
        sub,
        content=COMPANY_02_FILE.read_bytes(),
        filename=COMPANY_02_FILE.name,
        user_id=None,
    )
    template, parsed = mis_service.preview_submission(sub)
    assert template == "v2"
    assert len(parsed.monthly_rows) > 0


def test_unknown_template_raises(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_x", period_year=2025, period_month=6),
        user_id=None,
    )
    mis_service.attach_file(
        db, sub, content=_make_empty_xlsx(), filename="empty.xlsx", user_id=None
    )
    with pytest.raises(parser.UnknownTemplateError):
        mis_service.preview_submission(sub)


@pytest.mark.skipif(not COMPANY_01_FILE.exists(), reason="samples not mounted")
def test_approve_inserts_child_rows(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_01", period_year=2026, period_month=3),
        user_id=None,
    )
    mis_service.attach_file(
        db,
        sub,
        content=COMPANY_01_FILE.read_bytes(),
        filename=COMPANY_01_FILE.name,
        user_id=None,
    )
    sub = mis_service.approve_submission(db, sub, user_id=None)
    assert sub.status == "Approved"
    monthly = db.execute(
        select(MisMonthly).where(MisMonthly.submission_id == sub.id)
    ).scalars().all()
    bu = db.execute(
        select(MisBuMonthly).where(MisBuMonthly.submission_id == sub.id)
    ).scalars().all()
    assert len(monthly) > 0
    assert len(bu) > 0


@pytest.mark.skipif(not COMPANY_01_FILE.exists(), reason="samples not mounted")
def test_reapprove_replaces_child_rows(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_01", period_year=2026, period_month=3),
        user_id=None,
    )
    mis_service.attach_file(
        db,
        sub,
        content=COMPANY_01_FILE.read_bytes(),
        filename=COMPANY_01_FILE.name,
        user_id=None,
    )
    mis_service.approve_submission(db, sub, user_id=None)
    first_count = db.execute(
        select(MisMonthly).where(MisMonthly.submission_id == sub.id)
    ).scalars().all()
    mis_service.approve_submission(db, sub, user_id=None)
    second_count = db.execute(
        select(MisMonthly).where(MisMonthly.submission_id == sub.id)
    ).scalars().all()
    assert len(first_count) == len(second_count)


def test_reject_sets_status_and_reason(db: Session, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp_path)
    sub = mis_service.create_submission(
        db,
        MisSubmissionCreate(company_id="company_z", period_year=2025, period_month=7),
        user_id=None,
    )
    mis_service.attach_file(
        db, sub, content=b"junk", filename="junk.xlsx", user_id=None
    )
    sub = mis_service.reject_submission(
        db, sub, reason="Wrong period", user_id=None
    )
    assert sub.status == "Rejected"
    assert sub.rejection_reason == "Wrong period"
    monthly = db.execute(
        select(MisMonthly).where(MisMonthly.submission_id == sub.id)
    ).scalars().all()
    assert monthly == []
