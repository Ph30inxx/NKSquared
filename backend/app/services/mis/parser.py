"""Sprint 5 parser registry. Detects which template a workbook conforms to and
dispatches to the matching parser in `app.services.sample_loader`. Sprint 8's
visual template builder will replace the hard-coded detection.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from openpyxl import load_workbook

from app.services.sample_loader.mis_loader_v1 import (
    ParsedMisSubmission,
    load_mis_v1,
)
from app.services.sample_loader.mis_loader_v2 import load_mis_v2

TemplateName = Literal["v1", "v2"]

# Sheet names that uniquely identify each known template.
V1_SHEET = "Consolidated MIS FY 2026"
V2_SHEET = "MIS Report FY25-26"


class UnknownTemplateError(ValueError):
    """Raised when a workbook matches none of the known MIS templates."""


def detect_template(file_path: Path) -> TemplateName | None:
    try:
        wb = load_workbook(file_path, data_only=True, read_only=True)
    except Exception as exc:
        # openpyxl raises BadZipFile / InvalidFileException / KeyError on non-xlsx
        # input. Surface them as a recognizable parser error rather than a 500.
        raise UnknownTemplateError(
            f"Could not open workbook (not a valid .xlsx): {exc}"
        ) from exc
    try:
        names = set(wb.sheetnames)
    finally:
        wb.close()
    if V1_SHEET in names:
        return "v1"
    if V2_SHEET in names:
        return "v2"
    return None


def parse(file_path: Path, *, company_id: str) -> tuple[TemplateName, ParsedMisSubmission]:
    template = detect_template(file_path)
    if template is None:
        raise UnknownTemplateError(
            f"Template not recognized. Expected sheet {V1_SHEET!r} or {V2_SHEET!r}."
        )
    if template == "v1":
        return template, load_mis_v1(file_path, company_id=company_id)
    return template, load_mis_v2(file_path, company_id=company_id)
