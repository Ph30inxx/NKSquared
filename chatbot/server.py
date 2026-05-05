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
"""
import asyncio
import contextvars
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import psycopg2
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from chatbot.agents.coordinator import create_coordinator
from chatbot.config import DB_URL_SYNC, JWT_ALGORITHM, JWT_SECRET_KEY
from chatbot.context import reset_auth_token, set_auth_token
from chatbot.prompts import invalidate_prompt_cache

app = FastAPI(
    title="NKSquared Investment Intelligence Chatbot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

_bearer = HTTPBearer()


def get_current_user_id(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> int:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    response: str
    session_id: str


# ── DB helper ─────────────────────────────────────────────────────────────────

def _conn():
    return psycopg2.connect(DB_URL_SYNC)


# ── Conversation endpoints ────────────────────────────────────────────────────

@app.get("/conversations")
async def list_conversations(user_id: int = Depends(get_current_user_id)):
    """Return all conversations for the authenticated user, newest first."""
    conn = _conn()
    try:
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
    finally:
        conn.close()


@app.post("/conversations", status_code=201)
async def create_conversation(user_id: int = Depends(get_current_user_id)):
    """Create a new conversation and return its id and session_id."""
    conv_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_conversations (id, session_id, user_id, title) VALUES (%s, %s, %s, %s)",
                (conv_id, session_id, user_id, "New Conversation"),
            )
        conn.commit()
    finally:
        conn.close()
    return {"id": conv_id, "session_id": session_id, "title": "New Conversation"}


@app.delete("/conversations/{conv_id}", status_code=204)
async def delete_conversation(conv_id: str, user_id: int = Depends(get_current_user_id)):
    """Delete a conversation owned by the authenticated user."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM chat_conversations WHERE id = %s AND user_id = %s",
                (conv_id, user_id),
            )
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Conversation not found")
        conn.commit()
    finally:
        conn.close()


# ── Thread pool for blocking Agno calls ──────────────────────────────────────
# coordinator.run() is synchronous (Agno framework). Running it directly inside
# an async handler blocks the event loop, stalling all other requests and
# causing the Vite proxy / Azure to drop the connection on long queries.
_thread_pool = ThreadPoolExecutor(max_workers=10)


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
    # Validate JWT (same logic as get_current_user_id; inlined so we have the
    # raw token available for forwarding to the backend API in write tools).
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Store the raw token in a context var so write tools can forward it to
    # the backend API without it being passed as a parameter.
    _tok = set_auth_token(creds.credentials)

    try:
        session_id = request.session_id or str(uuid.uuid4())
        coordinator = create_coordinator(session_id=session_id)

        _touch_conversation(session_id, request.message)

        if request.stream:
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue[str | None] = asyncio.Queue()

            def _produce():
                try:
                    for chunk in coordinator.run(input=request.message, stream=True):
                        event_type = getattr(chunk, "event", None)
                        if event_type in ("run_response_content", "team_run_content", "TeamRunContent"):
                            content = getattr(chunk, "content", None)
                            if content:
                                loop.call_soon_threadsafe(
                                    queue.put_nowait, f"data: {json.dumps(content)}\n\n"
                                )
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, f"data: [ERROR] {exc}\n\n")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            # copy_context() snapshots the current ContextVar values (including
            # _auth_token) so they are visible inside the thread-pool thread.
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

        # Non-streaming: run_in_executor propagates context automatically.
        result = await asyncio.get_event_loop().run_in_executor(
            _thread_pool, lambda: coordinator.run(input=request.message, stream=False)
        )
        return ChatResponse(response=result.content, session_id=session_id)

    finally:
        reset_auth_token(_tok)


def _touch_conversation(session_id: str, message: str) -> None:
    """Update updated_at; set title from first user message if still default."""
    conn = _conn()
    try:
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
    finally:
        conn.close()


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

    Uses Team.get_chat_history() which is the correct Agno v2 API for Teams
    (Agents use get_messages_for_session() — different method).
    """
    coordinator = create_coordinator(session_id=session_id)
    try:
        raw = coordinator.get_chat_history(session_id=session_id) or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    messages = []
    for m in raw:
        role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": _extract_content(content)})

    return {"session_id": session_id, "messages": messages}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nksquared-chatbot"}


@app.post("/admin/reload-schema")
async def reload_schema(_: int = Depends(get_current_user_id)):
    """Force schema context and prompt cache to reload on next request."""
    invalidate_prompt_cache()
    return {"status": "schema cache cleared — will reload on next request"}
