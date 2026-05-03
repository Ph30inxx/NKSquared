"""
FastAPI chatbot server.
Endpoints: POST /chat  |  GET /session/{id}/history  |  GET /health
"""
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from chatbot.agents.coordinator import create_coordinator
from chatbot.prompts import invalidate_prompt_cache

app = FastAPI(
    title="NKSquared Investment Intelligence Chatbot",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = True


class ChatResponse(BaseModel):
    response: str
    session_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Text chat endpoint.

    - stream=True  → Server-Sent Events (SSE); response arrives word-by-word.
                     The X-Session-ID header carries the session id.
    - stream=False → Returns a ChatResponse JSON object synchronously.

    Pass the same session_id across turns to maintain conversation context.
    Omit it (or send null) to start a new conversation.
    """
    session_id  = request.session_id or str(uuid.uuid4())
    coordinator = create_coordinator(session_id=session_id)

    if request.stream:
        async def generate():
            try:
                for chunk in coordinator.run(input=request.message, stream=True):
                    # In Agno v2, we only want to yield the actual response content.
                    # We filter for 'run_response_content' (Agent) or 'team_run_content' (Team) events.
                    event_type = getattr(chunk, "event", None)
                    if event_type in ("run_response_content", "team_run_content", "TeamRunContent"):
                        content = getattr(chunk, "content", None)
                        if content:
                            import json
                            yield f"data: {json.dumps(content)}\n\n"
            except Exception as exc:
                yield f"data: [ERROR] {exc}\n\n"
            finally:
                yield "data: [DONE]\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"X-Session-ID": session_id},
        )

    result = coordinator.run(input=request.message, stream=False)
    return ChatResponse(response=result.content, session_id=session_id)


@app.get("/session/{session_id}/history")
async def session_history(session_id: str):
    """Return the stored conversation history for a session."""
    coordinator = create_coordinator(session_id=session_id)
    try:
        history = coordinator.get_messages_for_session()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"session_id": session_id, "messages": history}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "nksquared-chatbot"}


@app.post("/admin/reload-schema")
async def reload_schema():
    """
    Force the schema context and prompt cache to reload from PostgreSQL on the
    next request. Call this after running Alembic migrations without restarting
    the service.
    """
    invalidate_prompt_cache()
    return {"status": "schema cache cleared — will reload on next request"}
