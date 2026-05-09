"""
Dashboard assembly tool — compile_dashboard builds the HTML and renders it to PDF.
"""
import os
from datetime import datetime, timezone
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from chatbot.db import get_conn
from dashboard.config import DASHBOARD_STORAGE_PATH
from dashboard.tools.charts import get_chart, purge_dashboard


# Jinja2 environment
_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_jinja_env = Environment(loader=FileSystemLoader(_TEMPLATE_DIR))




def compile_dashboard(
    dashboard_id: str,
    title: str,
    subtitle: str,
    sections: List[dict],
    user_id: int,
    period_label: str = "",
    generated_by: str = "NKSquared AI",
) -> dict:
    """
    Compile all generated charts and text into a PDF report.

    Must be called EXACTLY ONCE per dashboard request, after all data has been
    fetched and all charts have been generated.

    Args:
        dashboard_id: The UUID of the current dashboard job.
        title: Dashboard title (e.g. "Portfolio Overview FY26").
        subtitle: Subtitle line (e.g. "Portfolio Overview — FY26").
        sections: Ordered list of section descriptors:
            {"type": "kpi",        "chart_id": "portfolio_kpis"}
            {"type": "chart",      "chart_id": "sector_bar", "caption": "..."}
            {"type": "chart_row",  "chart_ids": ["c01", "c02"], "captions": ["...", "..."]}
            {"type": "text",       "heading": "Overview", "body": "..."}
            {"type": "table",      "chart_id": "tx_table", "caption": "..."}
            {"type": "page_break"}
        user_id: Authenticated user — used to update dashboard_jobs.
        period_label: Human-readable period string shown in the header.
        generated_by: Attribution string in footer.

    Returns:
        {"status": "ready", "download_url": str, "page_count": int}
    """
    try:
        resolved_sections = _resolve_sections(dashboard_id, sections)
        html_str = _render_html(title, subtitle, period_label, generated_by, resolved_sections)
        pdf_bytes, page_count = _render_pdf(html_str)

        pdf_path = os.path.join(DASHBOARD_STORAGE_PATH, f"{dashboard_id}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        _update_job(dashboard_id, user_id, "ready", pdf_path, page_count, title, None)
        purge_dashboard(dashboard_id)

        return {
            "status": "ready",
            "download_url": f"/dashboard/{dashboard_id}/download",
            "page_count": page_count,
        }

    except Exception as exc:
        _update_job(dashboard_id, user_id, "failed", None, None, title, str(exc))
        raise


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_sections(dashboard_id: str, sections: List[dict]) -> List[dict]:
    """Pull base64 PNGs from chart store and build resolved section dicts."""
    resolved = []
    for s in sections:
        sec_type = s.get("type")

        if sec_type in ("kpi", "chart", "table"):
            chart_id = s.get("chart_id")
            b64 = get_chart(dashboard_id, chart_id) if chart_id else None
            resolved.append({
                **s,
                "base64_png": b64 or "",
            })

        elif sec_type == "chart_row":
            chart_ids = s.get("chart_ids", [])
            captions = s.get("captions", [""] * len(chart_ids))
            padded_captions = captions + [""] * len(chart_ids)

            # Charts that need full page width — never render side-by-side
            _FULL_WIDTH_CHARTS = {"waterfall", "scatter", "combo", "stacked_area", "area"}

            def _is_full_width(cid: str) -> bool:
                return any(k in cid.lower() for k in _FULL_WIDTH_CHARTS)

            if any(_is_full_width(cid) for cid in chart_ids):
                # Explode into individual full-width chart sections
                for cid, cap in zip(chart_ids, padded_captions):
                    b64 = get_chart(dashboard_id, cid)
                    resolved.append({
                        "type": "chart",
                        "chart_id": cid,
                        "base64_png": b64 or "",
                        "caption": cap,
                    })
            else:
                items = []
                for cid, cap in zip(chart_ids, padded_captions):
                    b64 = get_chart(dashboard_id, cid)
                    items.append({"chart_id": cid, "base64_png": b64 or "", "caption": cap})
                resolved.append({"type": "chart_row", "charts": items})

        else:
            resolved.append(s)

    return resolved


def _render_html(
    title: str,
    subtitle: str,
    period_label: str,
    generated_by: str,
    sections: List[dict],
) -> str:
    template = _jinja_env.get_template("dashboard.html")
    generated_at = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    return template.render(
        title=title,
        subtitle=subtitle,
        period_label=period_label,
        generated_by=generated_by,
        generated_at=generated_at,
        sections=sections,
    )


def _render_pdf(html_str: str) -> tuple[bytes, int]:
    """Render HTML to PDF using weasyprint. Returns (pdf_bytes, page_count)."""
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration

    font_config = FontConfiguration()
    doc = HTML(string=html_str).render(font_config=font_config)
    pdf_bytes = doc.write_pdf()
    page_count = len(doc.pages)
    return pdf_bytes, page_count


def _update_job(
    dashboard_id: str,
    user_id: int,
    status: str,
    pdf_path: str | None,
    page_count: int | None,
    title: str | None,
    error_msg: str | None,
) -> None:
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE dashboard_jobs
                    SET status=%s, pdf_path=%s, page_count=%s, title=%s,
                        error_msg=%s, completed_at=NOW()
                    WHERE id=%s AND user_id=%s
                """, (status, pdf_path, page_count, title, error_msg, dashboard_id, user_id))
            conn.commit()
    except Exception:
        pass  # don't mask the original exception
