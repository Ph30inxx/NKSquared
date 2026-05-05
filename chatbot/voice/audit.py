"""Per-tool-call and call-end audit logging to voice_call_logs table.

All DB writes are submitted to a small background thread pool so they
never block the async event loop or delay the tool response to Vapi.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from chatbot.db import get_conn, get_cursor
from chatbot.voice.models import CallSession

logger = logging.getLogger("nk.chatbot.voice.audit")

# Dedicated pool for audit writes — fire-and-forget, never blocks tool response.
_audit_pool = ThreadPoolExecutor(max_workers=2)


def _log_tool_call_sync(
    call_id: str,
    tool_name: str,
    user_query: str,
    result_preview: str,
    latency_ms: int,
    user_id: int,
) -> None:
    """Sync worker — runs inside _audit_pool thread."""
    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO voice_call_logs
                    (call_id, tool_name, user_query, result_preview, latency_ms, user_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (call_id, tool_name, user_query, result_preview[:200], latency_ms, user_id),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to log voice tool call: %s", exc)


def _log_call_end_sync(session: CallSession, duration_seconds: int) -> None:
    """Sync worker — runs inside _audit_pool thread."""
    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO voice_call_logs
                    (call_id, tool_name, user_query, result_preview, latency_ms, user_id, created_at)
                VALUES (%s, 'call_ended', '', %s, 0, %s, NOW())
                """,
                (
                    session.call_id,
                    f"turns={session.turn_count} duration={duration_seconds}s",
                    session.user_id,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to log call end: %s", exc)


def _save_transcript_sync(call_id: str, transcript: str, summary: str) -> None:
    """Sync worker — runs inside _audit_pool thread."""
    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            cur.execute(
                """
                INSERT INTO voice_call_logs
                    (call_id, tool_name, user_query, result_preview, latency_ms, user_id, created_at)
                VALUES (%s, 'end_of_call_transcript', %s, %s, 0, 0, NOW())
                """,
                (call_id, transcript[:4000], summary[:500]),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Failed to persist end-of-call transcript: %s", exc)


# ── Public async API (signatures unchanged so callers don't need updating) ────
# Each submits to the thread pool and returns immediately — fire-and-forget.

async def log_voice_tool_call(
    call_id: str,
    tool_name: str,
    user_query: str,
    result_preview: str,
    latency_ms: int,
    user_id: int,
) -> None:
    """
    Log each voice tool call durably.

    This is the backup transcript. If the call drops before Vapi sends
    end-of-call-report, voice_call_logs still has a per-turn record of
    every query and result, independent of call completion.
    """
    _audit_pool.submit(
        _log_tool_call_sync,
        call_id, tool_name, user_query, result_preview, latency_ms, user_id,
    )


async def log_voice_call_end(session: CallSession, duration_seconds: int) -> None:
    _audit_pool.submit(_log_call_end_sync, session, duration_seconds)


async def save_voice_call_transcript(call_id: str, transcript: str, summary: str) -> None:
    """Persist the full call transcript from Vapi's end-of-call-report."""
    _audit_pool.submit(_save_transcript_sync, call_id, transcript, summary)
