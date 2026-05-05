"""Redis-backed voice call session store."""
import asyncio
import logging
import redis.asyncio as aioredis

from chatbot.config import REDIS_URL
from chatbot.voice.models import CallSession

logger = logging.getLogger("nk.chatbot.voice.session_store")

_SESSION_KEY = "nk:voice:session:{}"
_SESSION_TTL = 7200  # 2 hours

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def get_call_session(
    call_id: str, retries: int = 5, delay_ms: int = 300
) -> CallSession | None:
    """Fetch session with retry.

    Vapi can fire tool-calls before status-update:in-progress on inbound calls.
    The retry gives handle_call_started() time to write the session first.
    """
    r = _get_redis()
    key = _SESSION_KEY.format(call_id)
    for attempt in range(retries):
        try:
            raw = await r.get(key)
        except Exception as exc:
            logger.warning("Redis GET failed (attempt %d/%d): %s", attempt + 1, retries, exc)
            raw = None
        if raw:
            return CallSession.model_validate_json(raw)
        if attempt < retries - 1:
            await asyncio.sleep(delay_ms / 1000)

    logger.warning("Session not found after %d retries: call_id=%s key=%s", retries, call_id, key)
    return None


async def set_call_session(session: CallSession) -> None:
    r = _get_redis()
    await r.set(
        _SESSION_KEY.format(session.call_id),
        session.model_dump_json(),
        ex=_SESSION_TTL,
    )


async def delete_call_session(call_id: str) -> None:
    r = _get_redis()
    await r.delete(_SESSION_KEY.format(call_id))
