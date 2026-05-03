"""Local-disk store for uploaded MIS workbooks. Sprint 8/post-pilot can swap to S3/MinIO."""
from __future__ import annotations

from pathlib import Path

UPLOAD_DIR = Path("/data/mis_uploads")


def upload_path(submission_id: int) -> Path:
    return UPLOAD_DIR / f"{submission_id}.xlsx"


def save_uploaded_file(submission_id: int, content: bytes) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = upload_path(submission_id)
    path.write_bytes(content)
    return path


def read_uploaded_file(submission_id: int) -> bytes:
    return upload_path(submission_id).read_bytes()


def delete_uploaded_file(submission_id: int) -> None:
    p = upload_path(submission_id)
    if p.exists():
        p.unlink()
