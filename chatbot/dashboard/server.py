"""
Dashboard FastAPI router — 4 endpoints + SSE streaming.

Endpoints:
  POST  /dashboard/generate          Start dashboard generation (SSE stream)
  GET   /dashboard/{id}/status       Poll job status
  GET   /dashboard/{id}/download     Download the generated PDF
  GET   /dashboard/history           List user's past dashboards
"""
import asyncio
import contextvars
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from chatbot.auth import get_current_user_id
from chatbot.db import get_conn
from dashboard.agents.dashboard import create_dashboard_agent
from dashboard.config import DASHBOARD_STORAGE_PATH

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_thread_pool = ThreadPoolExecutor(max_workers=5)


# ── Request models ────────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    query: str


# ── DB helpers ────────────────────────────────────────────────────────────────

def _create_job(user_id: int, query: str) -> str:
    job_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dashboard_jobs (id, user_id, query, status)
                VALUES (%s, %s, %s, 'generating')
            """, (job_id, user_id, query[:2000]))
        conn.commit()
    return job_id


def _get_job(dashboard_id: str, user_id: int) -> Optional[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, user_id, query, title, status, pdf_path,
                       page_count, error_msg, created_at, completed_at
                FROM dashboard_jobs
                WHERE id=%s AND user_id=%s
            """, (dashboard_id, user_id))
            row = cur.fetchone()
    return dict(row) if row else None


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_dashboard(
    request: GenerateRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Start a new dashboard generation job and stream progress via SSE.

    Events:
        {type: "started",   dashboard_id}
        {type: "tool_call", tool, status: "running"|"done", chart_id?}
        {type: "complete",  dashboard_id, download_url, title, page_count}
        {type: "error",     message}
    """
    dashboard_id = _create_job(user_id, request.query)

    async def _stream():
        yield _sse({"type": "started", "dashboard_id": dashboard_id})

        loop = asyncio.get_event_loop()
        event_queue: asyncio.Queue = asyncio.Queue()

        def _run():
            try:
                agent = create_dashboard_agent(dashboard_id, user_id)

                # Intercept tool call events by wrapping tool functions.
                # Agno fires show_tool_calls output to stdout; we hook the queue
                # via a simple response iteration approach.
                response = agent.run(input=request.query, stream=False)

                # Extract final result from agent response
                content = getattr(response, "content", None) or str(response)

                # Look for download_url in agent output or check DB
                result = _get_job(dashboard_id, user_id)
                if result and result.get("status") == "ready":
                    loop.call_soon_threadsafe(event_queue.put_nowait, {
                        "type": "complete",
                        "dashboard_id": dashboard_id,
                        "download_url": f"/dashboard/{dashboard_id}/download",
                        "title": result.get("title", "Dashboard"),
                        "page_count": result.get("page_count", 0),
                        "summary": content,
                    })
                else:
                    error_msg = result.get("error_msg", "Generation failed") if result else "Unknown error"
                    loop.call_soon_threadsafe(event_queue.put_nowait, {
                        "type": "error",
                        "message": error_msg,
                    })

            except Exception as exc:
                loop.call_soon_threadsafe(event_queue.put_nowait, {
                    "type": "error",
                    "message": str(exc),
                })
            finally:
                loop.call_soon_threadsafe(event_queue.put_nowait, None)

        _thread_pool.submit(contextvars.copy_context().run, _run)

        # Poll the DB periodically and emit tool_call events while waiting
        last_tool_count = 0
        tool_names_seen: set = set()

        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=2.0)
                if event is None:
                    break
                yield _sse(event)
                if event.get("type") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                # Poll DB for tool activity (job status)
                job = _get_job(dashboard_id, user_id)
                if job and job.get("status") == "ready":
                    yield _sse({
                        "type": "complete",
                        "dashboard_id": dashboard_id,
                        "download_url": f"/dashboard/{dashboard_id}/download",
                        "title": job.get("title", "Dashboard"),
                        "page_count": job.get("page_count", 0),
                    })
                    break
                # Emit a heartbeat progress event
                yield _sse({"type": "heartbeat", "dashboard_id": dashboard_id})

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Dashboard-ID": dashboard_id,
        },
    )


@router.get("/history")
async def get_dashboard_history(user_id: int = Depends(get_current_user_id)):
    """Return the user's past dashboard jobs, newest first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, title, status, page_count, created_at, completed_at
                FROM dashboard_jobs
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT 50
            """, (user_id,))
            rows = cur.fetchall()

    return {
        "dashboards": [
            {
                "dashboard_id": str(r["id"]),
                "title": r["title"] or "Untitled Dashboard",
                "status": r["status"],
                "page_count": r["page_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "completed_at": r["completed_at"].isoformat() if r["completed_at"] else None,
                "download_url": f"/dashboard/{r['id']}/download" if r["status"] == "ready" else None,
            }
            for r in rows
        ]
    }


@router.get("/{dashboard_id}/status")
async def get_status(dashboard_id: str, user_id: int = Depends(get_current_user_id)):
    """Poll the status of a dashboard generation job."""
    job = _get_job(dashboard_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    return {
        "dashboard_id": str(job["id"]),
        "status": job["status"],
        "title": job.get("title"),
        "page_count": job.get("page_count"),
        "error_msg": job.get("error_msg"),
        "download_url": f"/dashboard/{dashboard_id}/download" if job["status"] == "ready" else None,
        "created_at": job["created_at"].isoformat() if job.get("created_at") else None,
        "completed_at": job["completed_at"].isoformat() if job.get("completed_at") else None,
    }


@router.get("/{dashboard_id}/download")
async def download_dashboard(dashboard_id: str, user_id: int = Depends(get_current_user_id)):
    """Download the generated PDF for a dashboard job."""
    job = _get_job(dashboard_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    if job["status"] != "ready":
        raise HTTPException(status_code=400, detail=f"Dashboard status is '{job['status']}', not ready")
    if not job.get("pdf_path"):
        raise HTTPException(status_code=404, detail="PDF file not found")

    import os
    if not os.path.exists(job["pdf_path"]):
        raise HTTPException(status_code=404, detail="PDF file missing from storage")

    safe_title = (job.get("title") or "dashboard").replace(" ", "_").replace("/", "-")[:60]
    filename = f"{safe_title}.pdf"

    return FileResponse(
        path=job["pdf_path"],
        media_type="application/pdf",
        filename=filename,
    )
