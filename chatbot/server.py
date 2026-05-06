"""
FastAPI chatbot server.

Endpoints:
  POST   /chat
  GET    /session/{id}/history
  GET    /conversations
  POST   /conversations
  DELETE /conversations/{id}
  GET    /health
  POST   /admin/reload-schema

Optimisations applied (v2):
  - Single Agent replaces Coordinator+Analyst Team (−2 LLM round-trips)
  - Agent instances cached per session (warm model connections)
  - Connection pooling via ThreadedConnectionPool (no fresh TCP per op)
  - _touch_conversation() is fire-and-forget (off critical path)
  - Dynamic tool pruning: write tools loaded only when write intent detected
  - Prompt structured for Azure OpenAI automatic prefix caching
"""
import asyncio
import contextvars
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

from agno.agent import Agent
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from chatbot.agents.intelligence import (
    create_intelligence_agent,
    needs_write_tools,
)
from chatbot.config import JWT_ALGORITHM, JWT_SECRET_KEY
from chatbot.context import reset_auth_token, set_auth_token
from chatbot.db import get_conn
from chatbot.auth import _bearer, get_current_user_id
from chatbot.prompts import invalidate_prompt_cache
from chatbot.voice.router import router as voice_router

app = FastAPI(
    title="NKSquared Investment Intelligence Chatbot",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(voice_router)

# _bearer and get_current_user_id are imported from chatbot.auth above


# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    response: str
    session_id: str


# ── Conversation endpoints ────────────────────────────────────────────────────

@app.get("/conversations")
async def list_conversations(user_id: int = Depends(get_current_user_id)):
    """Return all conversations for the authenticated user, newest first."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, session_id, title, created_at, updated_at
                FROM chat_conversations
                WHERE user_id = %s
                ORDER BY updated_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return [
        {
            "id": r["id"],
            "session_id": r["session_id"],
            "title": r["title"],
            "created_at": r["created_at"].isoformat(),
            "updated_at": r["updated_at"].isoformat(),
        }
        for r in rows
    ]


@app.post("/conversations", status_code=201)
async def create_conversation(user_id: int = Depends(get_current_user_id)):
    """Create a new conversation and return its id and session_id."""
    conv_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_conversations (id, session_id, user_id, title) VALUES (%s, %s, %s, %s)",
                (conv_id, session_id, user_id, "New Conversation"),
            )
        conn.commit()
    return {"id": conv_id, "session_id": session_id, "title": "New Conversation"}


class VoiceTurn(BaseModel):
    role: str
    content: str = ""   # null/undefined content from Vapi tool-call turns becomes ""


class VoiceConversationRequest(BaseModel):
    session_id: str
    title: str
    turns: list[VoiceTurn]


@app.post("/conversations/voice", status_code=201)
async def save_voice_conversation(
    req: VoiceConversationRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    Save a completed voice call as a conversation entry.

    Creates a chat_conversations row and stores each turn in
    voice_chat_messages (created lazily on first use — no migration needed).
    The GET /session/{id}/history endpoint checks this table first, so
    clicking the voice entry in the sidebar loads the full transcript.
    """
    conv_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS voice_chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ord INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_vcm_session_id
                    ON voice_chat_messages(session_id)
            """)
            cur.execute(
                "INSERT INTO chat_conversations (id, session_id, user_id, title) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (session_id) DO NOTHING",
                (conv_id, req.session_id, user_id, req.title[:80]),
            )
            # Only insert turns if the conversation row was actually new
            if cur.rowcount > 0:
                for i, turn in enumerate(req.turns):
                    cur.execute(
                        "INSERT INTO voice_chat_messages (session_id, role, content, ord) VALUES (%s, %s, %s, %s)",
                        (req.session_id, turn.role, turn.content, i),
                    )
        conn.commit()
    return {
        "id": conv_id,
        "session_id": req.session_id,
        "title": req.title[:80],
        "created_at": now,
        "updated_at": now,
    }


@app.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(conv_id: str, user_id: int = Depends(get_current_user_id)):
    """Delete a conversation owned by the authenticated user."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_conversations WHERE id = %s AND user_id = %s",
                (conv_id, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Conversation not found")
        conn.commit()


# ── Agent cache ───────────────────────────────────────────────────────────────
# Agents are cached per session_id to reuse warm Azure OpenAI HTTP pools,
# SQLTools engines, and PostgresDb storage objects across turns.

_agent_cache: dict[str, tuple[Agent, bool]] = {}  # session_id → (agent, has_write_tools)
_cache_lock = threading.Lock()
_MAX_CACHED_AGENTS = 100


def _get_or_create_agent(session_id: str, include_write: bool = False) -> Agent:
    """
    Return a cached agent for this session, creating one if needed.

    If a read-only agent is cached but write tools are now needed,
    the agent is recreated with the full tool set. Both share the same
    session storage table so conversation history is preserved.
    """
    cached = _agent_cache.get(session_id)
    if cached:
        agent, has_write = cached
        if not include_write or has_write:
            return agent
        # Need write tools but cached agent is read-only — recreate

    with _cache_lock:
        # Double-check under lock
        cached = _agent_cache.get(session_id)
        if cached:
            agent, has_write = cached
            if not include_write or has_write:
                return agent

        # Evict oldest if at capacity
        if len(_agent_cache) >= _MAX_CACHED_AGENTS:
            oldest_key = next(iter(_agent_cache))
            del _agent_cache[oldest_key]

        agent = create_intelligence_agent(
            session_id=session_id,
            include_write_tools=include_write,
        )
        _agent_cache[session_id] = (agent, include_write)
        return agent


# ── Thread pool for blocking Agno calls ──────────────────────────────────────
# Agent.run() is synchronous (Agno framework). Running it directly inside
# an async handler blocks the event loop, stalling all other requests.
_thread_pool = ThreadPoolExecutor(max_workers=10)


# ── Greeting / chitchat fast-path ─────────────────────────────────────────────
# Bypass the entire LLM pipeline for trivial messages. Saves a full LLM
# round-trip (~2-4s) that would only produce a canned greeting anyway.

_GREETING_PATTERNS = frozenset({
    "hi", "hey", "hello", "hii", "hiii", "yo", "sup",
    "good morning", "good afternoon", "good evening",
    "gm", "morning", "afternoon", "evening",
})

_THANKS_PATTERNS = frozenset({
    "thanks", "thank you", "thankyou", "thx", "ty",
    "thanks!", "thank you!", "great thanks", "perfect thanks",
    "awesome thanks", "ok thanks", "okay thanks",
    "cool", "got it", "noted", "ok", "okay", "alright",
})

_SCOPE_PATTERNS = frozenset({
    "what can you do", "what do you do", "who are you",
    "help", "what are you", "what is this",
})

_GREETING_RESPONSE = (
    "Hello! 👋 I'm the NKSquared Investment Intelligence assistant. I can help you with:\n\n"
    "• **Portfolio overview** — MOIC, IRR, sector breakdown, alerts\n"
    "• **Company deep-dives** — valuations, transactions, performance\n"
    "• **MIS data** — revenue, EBITDA, BU/outlet breakdowns, trends\n"
    "• **Write operations** — log transactions, update companies, correct data\n\n"
    "What would you like to know?"
)

_THANKS_RESPONSE = "You're welcome! Let me know if you need anything else. 😊"

_SCOPE_RESPONSE = _GREETING_RESPONSE  # Same helpful message


def _check_fast_path(message: str) -> str | None:
    """Return an instant response for trivial messages, or None to proceed to the agent."""
    normalised = message.strip().lower().rstrip("!?.").strip()
    if normalised in _GREETING_PATTERNS:
        return _GREETING_RESPONSE
    if normalised in _THANKS_PATTERNS:
        return _THANKS_RESPONSE
    if normalised in _SCOPE_PATTERNS:
        return _SCOPE_RESPONSE
    return None


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(request: ChatRequest, creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    """
    Text chat endpoint.

    - stream=True  → Server-Sent Events (SSE); response arrives word-by-word.
                     The X-Session-ID header carries the session id.
    - stream=False → Returns a ChatResponse JSON object synchronously.

    Pass the same session_id across turns to maintain conversation context.
    Omit it (or send null) to start a new conversation.
    """
    # Validate JWT (inlined so we have the raw token for write tools).
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    session_id = request.session_id or str(uuid.uuid4())

    # ── Fast-path: greetings, thanks, meta-questions ──────────────────────
    # No LLM call, no tool loading, no DB hit — instant response.
    fast_reply = _check_fast_path(request.message)
    if fast_reply:
        _thread_pool.submit(_touch_conversation, session_id, request.message)
        if request.stream:
            async def _greeting_stream():
                yield f"data: {json.dumps(fast_reply)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(
                _greeting_stream(),
                media_type="text/event-stream",
                headers={"X-Session-ID": session_id},
            )
        return ChatResponse(response=fast_reply, session_id=session_id)

    # ── Full agent pipeline ───────────────────────────────────────────────
    # Store raw token in context var for write tools.
    _tok = set_auth_token(creds.credentials)

    try:
        # Detect write intent for dynamic tool pruning
        include_write = needs_write_tools(request.message)
        agent = _get_or_create_agent(session_id, include_write=include_write)

        # Fire-and-forget: update conversation metadata off the critical path
        _thread_pool.submit(_touch_conversation, session_id, request.message)

        if request.stream:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def _produce():
                try:
                    run_input = (
                        "[Format Request: Please provide a bit detailed response using rich Markdown, "
                        "data tables, formulas (if applicable) and analysis.]\n"
                        f"{request.message}"
                    )
                    for chunk in agent.run(input=run_input, stream=True):
                        content = getattr(chunk, "content", None)
                        if content:
                            loop.call_soon_threadsafe(
                                queue.put_nowait, f"data: {json.dumps(content)}\n\n"
                            )
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, f"data: [ERROR] {exc}\n\n")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            # copy_context() snapshots ContextVar values (including _auth_token)
            # so they are visible inside the thread-pool thread.
            _thread_pool.submit(contextvars.copy_context().run, _produce)

            async def generate():
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    yield item
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers={"X-Session-ID": session_id},
            )

        # Non-streaming path
        run_input = (
            "[Format Request: Please provide a bit detailed response using rich Markdown, "
            "data tables, formulas (if applicable) and analysis.]\n"
            f"{request.message}"
        )
        result = await asyncio.get_event_loop().run_in_executor(
            _thread_pool, lambda: agent.run(input=run_input, stream=False)
        )
        return ChatResponse(response=result.content, session_id=session_id)

    finally:
        reset_auth_token(_tok)


def _touch_conversation(session_id: str, message: str) -> None:
    """Update updated_at; set title from first user message if still default.

    Runs in background thread — errors are swallowed to avoid breaking chat.
    """
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT title FROM chat_conversations WHERE session_id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if not row:
                    return
                if row["title"] == "New Conversation" and not message.startswith("[SYSTEM:"):
                    title = message[:60].replace("\n", " ")
                    cur.execute(
                        "UPDATE chat_conversations SET title = %s, updated_at = NOW() WHERE session_id = %s",
                        (title, session_id),
                    )
                else:
                    cur.execute(
                        "UPDATE chat_conversations SET updated_at = NOW() WHERE session_id = %s",
                        (session_id,),
                    )
            conn.commit()
    except Exception:
        pass  # best-effort; don't break chat on a metadata failure


# ── Utility endpoints ─────────────────────────────────────────────────────────

def _extract_content(content) -> str:
    """Normalise Agno/OpenAI content — handles str, list-of-blocks, or None."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
        return "".join(parts)
    return str(content) if content is not None else ""


@app.get("/session/{session_id}/history")
async def session_history(session_id: str, _: int = Depends(get_current_user_id)):
    """Return the stored conversation history for a session.

    Checks voice_chat_messages first (voice calls saved from VoicePage).
    Falls back to Agno session storage for text chat sessions.
    """
    # Voice conversations are stored in voice_chat_messages — check first
    try:
        with get_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT role, content FROM voice_chat_messages "
                    "WHERE session_id = %s ORDER BY ord ASC",
                    (session_id,),
                )
                voice_rows = cur.fetchall()
        if voice_rows:
            return {
                "session_id": session_id,
                "messages": [{"role": r["role"], "content": r["content"]} for r in voice_rows],
            }
    except Exception:
        pass  # table may not exist on older deployments — fall through

    # Text chat: load from Agno session storage
    agent = _get_or_create_agent(session_id, include_write=False)
    try:
        raw = agent.get_session_messages(session_id=session_id) or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    messages = []
    for m in raw:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if role in ("user", "assistant"):
            clean_content = _extract_content(content)
            if clean_content.startswith("[Format Request:"):
                clean_content = clean_content.split("]\n", 1)[-1]
            elif clean_content.startswith("[TEXT CHAT MODE"):
                clean_content = clean_content.split("]\n", 1)[-1]
            elif clean_content.startswith("[VOICE MODE"):
                clean_content = clean_content.split("] ", 1)[-1]
            messages.append({"role": role, "content": clean_content})

    return {"session_id": session_id, "messages": messages}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nksquared-chatbot"}


@app.post("/admin/reload-schema")
async def reload_schema(_: int = Depends(get_current_user_id)):
    """Force schema context and prompt cache to reload on next request."""
    # Also clear the agent cache so agents pick up the new prompts
    with _cache_lock:
        _agent_cache.clear()
    invalidate_prompt_cache()
    return {"status": "schema cache cleared — will reload on next request"}
