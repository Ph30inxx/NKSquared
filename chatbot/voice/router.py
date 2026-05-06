"""
Vapi server-side event handler for NKSquared voice chatbot.

Mounted at /vapi/server and /voice/session.
Handles: tool-calls, status-update (in-progress / ended), end-of-call-report.

Two Vapi tools:
  query_investment_data      — all reads, routes to Agno coordinator
  execute_investment_action  — all writes (verbal confirmation already obtained by
                               the Vapi model before this fires), mints a service
                               JWT and routes to Agno coordinator
"""
import asyncio
import contextvars
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date as _date

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from jose import jwt as jose_jwt
from pydantic import BaseModel

from chatbot.agents.intelligence import create_intelligence_agent, needs_write_tools
from chatbot.auth import get_current_user_id
from chatbot.config import (
    JWT_ALGORITHM,
    JWT_SECRET_KEY,
    VAPI_ASSISTANT_ID,
    VAPI_SERVER_AUTH_DISABLED,
    VAPI_SHARED_SECRET,
)
from chatbot.context import reset_auth_token, set_auth_token
from chatbot.voice.audit import (
    log_voice_call_end,
    log_voice_tool_call,
    save_voice_call_transcript,
)
from chatbot.voice.models import CallSession
from chatbot.voice.response_compressor import compress_for_voice
from chatbot.voice.session_store import (
    delete_call_session,
    get_call_session,
    set_call_session,
)

logger = logging.getLogger("nk.chatbot.voice.router")
router = APIRouter(tags=["voice"])

# Agno coordinator.run() is synchronous — same pattern as server.py.
# Increased from 5 → 10 to avoid queueing under concurrent voice calls.
_voice_pool = ThreadPoolExecutor(max_workers=10)

# Queries containing these words get more sentences in the compressed response.
_SUMMARY_KEYWORDS = {
    "summary", "overview", "trend", "breakdown", "briefing", "alerts",
    "performance", "compare", "analysis", "all", "full", "detail", "report",
}

# ── Voice agent cache ─────────────────────────────────────────────────────────
# Mirrors the _agent_cache in server.py but for the voice path.
# Avoids recreating Agent (new HTTP client, DB conn, SQLTools) on every tool call.

_voice_agent_cache: dict[str, tuple] = {}   # session_id → (agent, has_write_tools)
_voice_cache_lock = threading.Lock()
_MAX_VOICE_AGENTS = 50


def _get_or_create_voice_agent(session_id: str, include_write: bool = False):
    """Return a cached agent for this voice session, creating one if needed."""
    cached = _voice_agent_cache.get(session_id)
    if cached:
        agent, has_write = cached
        if not include_write or has_write:
            return agent

    with _voice_cache_lock:
        # Double-check under lock
        cached = _voice_agent_cache.get(session_id)
        if cached:
            agent, has_write = cached
            if not include_write or has_write:
                return agent

        if len(_voice_agent_cache) >= _MAX_VOICE_AGENTS:
            oldest_key = next(iter(_voice_agent_cache))
            del _voice_agent_cache[oldest_key]

        agent = create_intelligence_agent(
            session_id=session_id,
            include_write_tools=include_write,
        )
        _voice_agent_cache[session_id] = (agent, include_write)
        return agent


# ── JWT helper ────────────────────────────────────────────────────────────────

def _voice_jwt(user_id: int) -> str:
    """Mint a short-lived JWT for voice write calls on behalf of user_id.

    In voice, Vapi calls our server directly — there is no browser JWT in the
    request. We generate one from the user_id stored in the Redis CallSession so
    write tools can authenticate against the backend API with the correct analyst
    identity. The backend audit_log will show the right user email.
    """
    return jose_jwt.encode(
        {"sub": str(user_id), "type": "access"},
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


# ── Vapi server handler ───────────────────────────────────────────────────────

@router.post("/vapi/server")
async def vapi_server_handler(
    request: Request,
    x_vapi_secret: str = Header(None, alias="x-vapi-secret"),
):
    """Unified Vapi server-side event handler."""
    if not VAPI_SERVER_AUTH_DISABLED:
        if x_vapi_secret != VAPI_SHARED_SECRET:
            raise HTTPException(status_code=401)

    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type")

    if msg_type == "tool-calls":
        return await _handle_tool_calls(message)

    if msg_type == "status-update":
        status = message.get("status")
        if status == "in-progress":
            await _handle_call_started(message)
        elif status in ("ended", "forwarded"):
            await _handle_call_ended(message)
        return {"received": True}

    if msg_type == "end-of-call-report":
        await _handle_end_of_call_report(message)
        return {"received": True}

    return {"received": True}


# ── Tool call dispatcher ──────────────────────────────────────────────────────

async def _handle_tool_calls(message: dict) -> dict:
    call = message.get("call", {})
    call_id = call.get("id", "unknown")
    session = await get_call_session(call_id)

    if session is None:
        logger.warning(
            "tool-calls fired before session ready for call_id=%s. "
            "call keys=%s",
            call_id, list(call.keys()),
        )

        # Vapi nests variableValues differently across event types.
        # Try every known location before giving up.
        variables: dict = {}
        for path in [
            lambda: call.get("assistantOverrides", {}).get("variableValues", {}),
            lambda: call.get("variableValues", {}),
            # Some Vapi versions put it under assistant → not assistantOverrides
            lambda: call.get("assistant", {}).get("variableValues", {}),
        ]:
            variables = path()
            if variables:
                break

        # Last resort: check the Vapi message root (some webhooks put it there)
        if not variables:
            variables = message.get("call", {}).get("assistantOverrides", {}).get("variableValues", {})

        raw_user_id = str(variables.get("user_id", "")).strip()
        session_id = str(variables.get("session_id", "")).strip()
        user_id_missing = not raw_user_id or not session_id

        if user_id_missing:
            logger.error(
                "tool-calls: no session in Redis AND no variables in payload. "
                "call_id=%s, call_obj=%s",
                call_id,
                json.dumps(call, default=str)[:500],
            )
            return {
                "results": [
                    {"toolCallId": tc["id"], "result": "I am not ready yet. Please try again."}
                    for tc in message.get("toolCallList", [])
                ]
            }

        session = CallSession(
            call_id=call_id,
            user_id=int(raw_user_id) if raw_user_id.isdigit() else 0,
            session_id=session_id,
            user_id_missing=False,
        )
        await set_call_session(session)
        logger.info("Lazy-created voice session: call_id=%s user_id=%s", call_id, session.user_id)

    results = []

    # Vapi sends both toolCallList and toolWithToolCallList — prefer the former
    # but normalise from the latter if needed.
    raw_tool_calls = message.get("toolCallList", [])
    if not raw_tool_calls:
        # toolWithToolCallList has shape: [{"name":"fn","toolCall":{"id":"...","parameters":{...}}}]
        # Normalise to the flat toolCallList shape.
        for item in message.get("toolWithToolCallList", []):
            tc = item.get("toolCall", {})
            raw_tool_calls.append({
                "id": tc.get("id", ""),
                "name": item.get("name", ""),
                "arguments": tc.get("parameters", {}),
            })

    for tool_call in raw_tool_calls:
        # ── Extract tool name and arguments ─────────────────────────────
        # Vapi's documented format puts name/arguments at the top level:
        #   { "id": "...", "name": "fn_name", "arguments": {...} }
        # But some Vapi versions / the toolWithToolCallList path use an
        # OpenAI-style wrapper:
        #   { "id": "...", "function": { "name": "fn_name", "arguments": {...} } }
        # Handle both.
        fn_block = tool_call.get("function")
        if fn_block and isinstance(fn_block, dict):
            tool_name = fn_block.get("name", "")
            raw_args = fn_block.get("arguments", {})
        else:
            tool_name = tool_call.get("name", "")
            raw_args = tool_call.get("arguments", tool_call.get("parameters", {}))

        if isinstance(raw_args, str):
            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}
        else:
            args = raw_args if isinstance(raw_args, dict) else {}

        # Vapi uses "id" at the top level; some wrappers nest it under toolCall
        tool_call_id = tool_call.get("id", "")

        if not tool_name:
            logger.warning("tool-calls item has no tool name: %s", json.dumps(tool_call, default=str)[:300])
            results.append({"toolCallId": tool_call_id, "result": "Could not determine the action. Please try again."})
            continue

        t0 = time.monotonic()

        if tool_name == "query_investment_data":
            result = await _tool_query(args, session)
        elif tool_name == "execute_investment_action":
            result = await _tool_execute(args, session)
        else:
            result = "I do not know how to handle that request."

        latency_ms = int((time.monotonic() - t0) * 1000)
        session.turn_count += 1
        await set_call_session(session)

        await log_voice_tool_call(
            call_id=call_id,
            tool_name=tool_name,
            user_query=args.get("query", ""),
            result_preview=result,
            latency_ms=latency_ms,
            user_id=session.user_id,
        )
        results.append({"toolCallId": tool_call_id, "result": result})

    return {"results": results}


# ── Tool: query_investment_data ───────────────────────────────────────────────

async def _tool_query(args: dict, session: CallSession) -> str:
    """Route any investment question through the Agno coordinator."""
    if session.user_id_missing:
        return "I cannot retrieve data right now. The session was not set up correctly."

    query = args.get("query", "")
    if not query:
        return "I did not catch the question. Could you repeat that?"

    is_summary = any(kw in query.lower() for kw in _SUMMARY_KEYWORDS)
    max_sentences = 4 if is_summary else 2

    try:
        loop = asyncio.get_event_loop()
        agent = _get_or_create_voice_agent(
            session.session_id,
            include_write=needs_write_tools(query),
        )
        today = _date.today().isoformat()
        voice_query = (
            f"[Today's date is {today}. VOICE MODE — respond in plain text only, no markdown, "
            f"{'3-4' if is_summary else '2'} sentences max] {query}"
        )

        # Run agent + compression together inside the thread pool so neither
        # blocks the async event loop.
        def _run():
            result = agent.run(input=voice_query, stream=False)
            text = result.content if result and result.content else ""
            if not text:
                return "I could not retrieve that information right now. Please try again."
            return compress_for_voice(text, max_sentences=max_sentences)

        return await asyncio.wait_for(
            loop.run_in_executor(_voice_pool, _run),
            timeout=55.0,
        )

    except asyncio.TimeoutError:
        logger.warning("Voice query timed out after 55s: %s", query[:80])
        return "That query took too long. Could you try a simpler question?"

    except Exception as exc:
        logger.error("Voice query handler error: %s", exc)
        return "Something went wrong retrieving that data. Please try again."


# ── Tool: execute_investment_action ──────────────────────────────────────────

async def _tool_execute(args: dict, session: CallSession) -> str:
    """
    Execute a confirmed write operation via the Agno coordinator.

    By the time this fires, the Vapi model has already verbally confirmed with
    the analyst. Verbal confirmation replaces the text chatbot's dry_run preview.

    All 10 write operations are supported — including:
      - log_transaction, add_valuation, update_company, upsert_forex_rate
      - send_mis_reminder, create_company
      - correct_mis_metric, correct_transaction, deactivate_company
      - manage_reminder_schedule

    Flow:
      1. Mint a service JWT for session.user_id (no browser token in voice path)
      2. Set in context var so write tools can call the backend API
      3. Snapshot context so the JWT propagates into the thread-pool thread
      4. Route to coordinator with confirmed-execution instruction
      5. Compress result to 1 spoken sentence
    """
    if session.user_id_missing:
        return "I cannot perform actions right now. The session was not set up correctly."

    query = args.get("query", "")
    if not query:
        return "I did not catch what action to perform. Could you repeat that?"

    token_reset = set_auth_token(_voice_jwt(session.user_id))

    try:
        loop = asyncio.get_event_loop()
        agent = _get_or_create_voice_agent(
            session.session_id,
            include_write=True,
        )
        # Verbal confirmation already obtained — skip the dry_run preview step.
        # Always inject today's date so "today" in the query resolves correctly
        # regardless of stale session history or model training data defaults.
        today = _date.today().isoformat()
        confirmed_query = (
            f"[Today's date is {today}] "
            f"The analyst said yes, go ahead. Complete this action: {query}"
        )

        # Snapshot ContextVars (including _auth_token) so they are visible
        # inside the thread-pool thread — identical pattern to server.py.
        ctx = contextvars.copy_context()

        # Run agent + compression together inside the thread pool.
        def _run():
            result = agent.run(input=confirmed_query, stream=False)
            text = result.content if result and result.content else ""
            if not text:
                return "I could not complete that action right now. Please try again."
            return compress_for_voice(text, max_sentences=1)

        return await asyncio.wait_for(
            loop.run_in_executor(_voice_pool, lambda: ctx.run(_run)),
            timeout=55.0,
        )

    except asyncio.TimeoutError:
        logger.warning("Voice write timed out after 55s: %s", query[:80])
        return "That action took too long. Please try again or check the app."

    except Exception as exc:
        logger.error("Voice write handler error: %s", exc)
        return "Something went wrong. Please try again or check the app."

    finally:
        reset_auth_token(token_reset)


# ── Call lifecycle ────────────────────────────────────────────────────────────

async def _handle_call_started(message: dict) -> None:
    call = message.get("call", {})
    call_id = call.get("id")

    # Try multiple known paths for variableValues — Vapi nesting varies by version
    variables = call.get("assistantOverrides", {}).get("variableValues", {})
    if not variables:
        variables = call.get("variableValues", {})
    if not variables:
        variables = call.get("assistant", {}).get("variableValues", {})

    logger.info(
        "call_started: call_id=%s, variable_keys=%s, call_keys=%s",
        call_id, list(variables.keys()), list(call.keys()),
    )

    # Coerce to str first — Vapi may deliver variableValues as int depending
    # on SDK version.  Without str() a bare int would crash on .strip().
    raw_user_id = str(variables.get("user_id", "")).strip()
    session_id = str(variables.get("session_id", "")).strip()
    user_id_missing = not raw_user_id or not session_id

    if user_id_missing:
        logger.warning(
            "call_started missing variableValues: call_id=%s variables=%s — tools will return errors",
            call_id, variables,
        )

    session = CallSession(
        call_id=call_id,
        user_id=int(raw_user_id) if raw_user_id.isdigit() else 0,
        session_id=session_id,
        user_id_missing=user_id_missing,
    )
    await set_call_session(session)
    logger.info("Voice session stored in Redis: call_id=%s user_id=%s session_id=%s", call_id, session.user_id, session_id)


async def _handle_call_ended(message: dict) -> None:
    call_id = message.get("call", {}).get("id")
    session = await get_call_session(call_id)
    if session:
        await log_voice_call_end(session, duration_seconds=0)
    await delete_call_session(call_id)
    logger.info("Voice session ended: call_id=%s", call_id)


async def _handle_end_of_call_report(message: dict) -> None:
    call_id = message.get("call", {}).get("id", "unknown")
    transcript = message.get("transcript", "")
    summary = message.get("summary", "")
    if transcript:
        await save_voice_call_transcript(call_id, transcript, summary)


# ── /voice/session endpoint (called by frontend before starting a Vapi call) ──

class VoiceSessionRequest(BaseModel):
    session_id: str


@router.post("/voice/session")
async def create_voice_session(
    req: VoiceSessionRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Returns the Vapi public key, assistant ID, and user context so the frontend
    can start a Vapi call with the correct variableValues.
    """
    return {
        "vapi_public_key": os.getenv("VAPI_PUBLIC_KEY", ""),
        "assistant_id": VAPI_ASSISTANT_ID,
        "user_id": user_id,
        "session_id": req.session_id,
    }
