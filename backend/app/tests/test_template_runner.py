"""Sprint 8 — exercise template_runner against a synthesized workbook."""
from __future__ import annotations

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.models.mis_template import MisTemplate
from app.services.mis.template_runner import (
    TemplateRunError,
    parsed_to_dict,
    run_template,
)


def _write_test_workbook() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Custom MIS Sheet"
    # Row 1: a banner so the parser must skip it.
    ws.append(["Mock Co", None, None, None])
    # Row 2: header — labels + 3 month dates.
    ws.append([
        "Section",
        "Metric",
        datetime(2025, 4, 1),
        datetime(2025, 5, 1),
        datetime(2025, 6, 1),
    ])
    ws.append(["Income", "Net Revenue", 100, 110, 121])
    ws.append(["Income", "COGS", 60, 65, 70])
    ws.append(["Income", "Gross Margin", 40, 45, 51])
    ws.append(["Costs", "EBITDA", 10, 12, 15])
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    wb.save(tmp.name)
    return Path(tmp.name)


def _template() -> MisTemplate:
    return MisTemplate(
        company_id="company_test",
        name="Test mock",
        version=1,
        is_default=False,
        sheet_name_pattern="^Custom MIS Sheet$",
        header_row=2,
        period_orientation="columns",
        row_mappings=[
            {"label_regex": r"^Net Revenue$", "metric_code": "revenue_lacs", "label_col_index": 1},
            {"label_regex": r"^COGS$", "metric_code": "cogs_lacs", "label_col_index": 1},
            {"label_regex": r"^Gross Margin$", "metric_code": "gross_margin_lacs", "label_col_index": 1},
            {"label_regex": r"^EBITDA$", "metric_code": "ebitda_lacs", "label_col_index": 1},
        ],
    )


def test_template_runner_extracts_three_months() -> None:
    path = _write_test_workbook()
    try:
        parsed = run_template(path, _template())
    finally:
        path.unlink()

    assert parsed.company_id == "company_test"
    assert len(parsed.monthly_rows) == 3
    by_month = {r.month_date.isoformat(): r for r in parsed.monthly_rows}
    assert by_month["2025-04-01"].revenue_lacs == 100
    assert by_month["2025-04-01"].cogs_lacs == 60
    assert by_month["2025-05-01"].gross_margin_lacs == 45
    assert by_month["2025-06-01"].ebitda_lacs == 15
    # Headline period is the latest month seen.
    assert parsed.period_year == 2025
    assert parsed.period_month == 6


def test_parsed_to_dict_is_jsonable() -> None:
    path = _write_test_workbook()
    try:
        parsed = run_template(path, _template())
    finally:
        path.unlink()

    payload = parsed_to_dict(parsed)
    assert payload["period_year"] == 2025
    assert isinstance(payload["monthly_rows"], list)
    # Decimals serialized as strings, dates as ISO.
    first = payload["monthly_rows"][0]
    assert isinstance(first["revenue_lacs"], str)
    assert first["month_date"].startswith("2025-")


def test_template_runner_rejects_missing_mappings() -> None:
    path = _write_test_workbook()
    try:
        tpl = _template()
        tpl.row_mappings = []
        with pytest.raises(TemplateRunError):
            run_template(path, tpl)
    finally:
        path.unlink()


def test_template_runner_requires_company_id() -> None:
    path = _write_test_workbook()
    try:
        tpl = _template()
        tpl.company_id = None
        with pytest.raises(TemplateRunError):
            run_template(path, tpl)
    finally:
        path.unlink()
