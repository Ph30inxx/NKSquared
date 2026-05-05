from datetime import datetime
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import require_role
from app.db.session import get_db
from app.models.user import User
from app.services.exports.mis_export import (
    build_mis_bulk_workbook,
    build_mis_workbook,
)
from app.services.exports.portfolio_export import build_portfolio_workbook

router = APIRouter(prefix="/exports", tags=["exports"])

_reader = require_role(["ADMIN", "ANALYST", "VIEWER"])

_XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _stream_xlsx(payload: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(payload),
        media_type=_XLSX_CT,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class BulkMisRequest(BaseModel):
    company_ids: list[str] = Field(min_length=1, max_length=100)


@router.get("/portfolio.xlsx")
def export_portfolio(
    db: Session = Depends(get_db),
    _user: User = Depends(_reader),
) -> StreamingResponse:
    payload = build_portfolio_workbook(db)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return _stream_xlsx(payload, f"nksquared_portfolio_{stamp}.xlsx")


@router.get("/mis/{company_id}.xlsx")
def export_mis_for_company(
    company_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(_reader),
) -> StreamingResponse:
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id is required")
    payload = build_mis_workbook(db, company_id)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return _stream_xlsx(payload, f"mis_{company_id}_{stamp}.xlsx")


@router.post("/mis/bulk.xlsx")
def export_mis_bulk(
    payload: BulkMisRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(_reader),
) -> StreamingResponse:
    workbook_bytes = build_mis_bulk_workbook(db, payload.company_ids)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    return _stream_xlsx(workbook_bytes, f"mis_bulk_{stamp}.xlsx")
