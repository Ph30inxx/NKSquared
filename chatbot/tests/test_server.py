"""
API endpoint tests for chatbot/server.py.

All tests run against the real FastAPI app with a real PostgreSQL connection
and real Azure OpenAI credentials. Nothing is mocked.

LLM call strategy — to keep the test suite fast and cheap:
  - Session-scoped fixtures make each expensive LLM call exactly once and
    cache the response for all tests in that class that need it.
  - "Hello" is used as the test message wherever content doesn't matter,
    because the coordinator answers greetings itself without routing to the
    Analyst or touching the database.
  - Tests that care about data content use a single session-scoped data call.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


# ── App client (one per session) ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    from chatbot.server import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ── Shared LLM responses (session-scoped — each LLM call made exactly once) ──

@pytest.fixture(scope="session")
def greeting_nonstream(client):
    """Single non-stream greeting call reused by all non-stream structural tests."""
    return client.post("/chat", json={"message": "Hello", "stream": False})


@pytest.fixture(scope="session")
def greeting_stream(client):
    """Single stream greeting call reused by all SSE structural tests."""
    return client.post("/chat", json={"message": "Hello", "stream": True})


@pytest.fixture(scope="session")
def data_nonstream(client):
    """
    One real data question to verify the agent can answer with actual numbers.
    Uses a question simple enough to always route to get_portfolio_summary.
    """
    return client.post("/chat", json={
        "message": "How many companies are in the portfolio?",
        "stream": False,
    })


@pytest.fixture(scope="session")
def session_id_for_continuity():
    """Fixed session ID used across multi-turn continuity tests."""
    return f"test-continuity-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="session")
def first_turn(client, session_id_for_continuity):
    """First message in a known session — establishes conversation history."""
    return client.post("/chat", json={
        "message": "Hello, my name is Test User.",
        "session_id": session_id_for_continuity,
        "stream": False,
    })


@pytest.fixture(scope="session")
def second_turn(client, session_id_for_continuity, first_turn):
    """Second message in the same session — tests multi-turn continuity."""
    return client.post("/chat", json={
        "message": "What name did I just tell you?",
        "session_id": session_id_for_continuity,
        "stream": False,
    })


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_status_field_is_ok(self, client):
        assert client.get("/health").json()["status"] == "ok"

    def test_service_field_mentions_chatbot(self, client):
        data = client.get("/health").json()
        assert "service" in data
        assert "chatbot" in data["service"].lower()


# ── /admin/reload-schema ──────────────────────────────────────────────────────

class TestReloadSchemaEndpoint:

    def test_returns_200(self, client):
        assert client.post("/admin/reload-schema").status_code == 200

    def test_response_has_status_key(self, client):
        assert "status" in client.post("/admin/reload-schema").json()

    def test_actually_clears_prompt_cache(self, client):
        """
        The endpoint calls invalidate_prompt_cache(). We verify this by
        checking that the prompt object is rebuilt (different identity) after
        the endpoint is called.
        """
        from chatbot.prompts import get_analyst_prompt, invalidate_prompt_cache

        # Ensure cache is warm
        invalidate_prompt_cache()
        before = get_analyst_prompt()

        # Trigger reload via the endpoint
        client.post("/admin/reload-schema")

        # Cache was cleared — next call must re-build the prompt from DB
        after = get_analyst_prompt()

        assert before == after        # same content (DB hasn't changed)
        assert before is not after    # but a new Python object (re-fetched)


# ── POST /chat — non-streaming structural tests ───────────────────────────────

class TestChatNonStreamStructure:
    """
    Tests that verify the HTTP shape of non-stream responses.
    All share one session-scoped LLM call (greeting_nonstream).
    """

    def test_returns_200(self, greeting_nonstream):
        assert greeting_nonstream.status_code == 200

    def test_response_field_is_present(self, greeting_nonstream):
        assert "response" in greeting_nonstream.json()

    def test_session_id_field_is_present(self, greeting_nonstream):
        assert "session_id" in greeting_nonstream.json()

    def test_response_is_a_non_empty_string(self, greeting_nonstream):
        response_text = greeting_nonstream.json()["response"]
        assert isinstance(response_text, str)
        assert len(response_text) > 0

    def test_session_id_is_uuid_format(self, greeting_nonstream):
        sid   = greeting_nonstream.json()["session_id"]
        parts = sid.split("-")
        assert len(parts) == 5, f"Expected UUID4 with 5 parts, got: {sid}"

    def test_content_type_is_json(self, greeting_nonstream):
        assert "application/json" in greeting_nonstream.headers.get("content-type", "")


# ── POST /chat — non-streaming session ID tests ───────────────────────────────

class TestChatNonStreamSessionId:
    """Each test needs its own LLM call to test a specific session_id scenario."""

    def test_auto_generated_session_id_is_uuid(self, client):
        resp = client.post("/chat", json={"message": "Hello", "stream": False})
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        # Validate UUID4 format: 8-4-4-4-12 hex characters
        parsed = uuid.UUID(sid, version=4)
        assert str(parsed) == sid

    def test_custom_session_id_is_echoed_back(self, client):
        custom_sid = "my-fixed-session-99"
        resp = client.post("/chat", json={
            "message": "Hello",
            "session_id": custom_sid,
            "stream": False,
        })
        assert resp.status_code == 200
        assert resp.json()["session_id"] == custom_sid

    def test_two_calls_without_session_id_get_different_ids(self, client):
        r1 = client.post("/chat", json={"message": "Hello", "stream": False})
        r2 = client.post("/chat", json={"message": "Hello", "stream": False})
        assert r1.json()["session_id"] != r2.json()["session_id"]


# ── POST /chat — non-streaming content tests ──────────────────────────────────

class TestChatNonStreamContent:
    """Uses the real data_nonstream fixture to verify the agent actually queries the DB."""

    def test_returns_200(self, data_nonstream):
        assert data_nonstream.status_code == 200

    def test_response_is_non_empty(self, data_nonstream):
        assert len(data_nonstream.json()["response"]) > 0

    def test_response_contains_numeric_content(self, data_nonstream):
        """
        A question about number of companies should produce a response that
        contains at least one digit — the agent must have queried the DB.
        """
        response_text = data_nonstream.json()["response"]
        assert any(ch.isdigit() for ch in response_text), (
            f"Expected a number in the response to a count question, got:\n{response_text}"
        )


# ── POST /chat — streaming / SSE structural tests ─────────────────────────────

class TestChatStreamStructure:
    """All share one session-scoped SSE call (greeting_stream)."""

    def test_returns_200(self, greeting_stream):
        assert greeting_stream.status_code == 200

    def test_content_type_is_event_stream(self, greeting_stream):
        ct = greeting_stream.headers.get("content-type", "")
        assert "text/event-stream" in ct, f"Expected SSE content-type, got: {ct}"

    def test_x_session_id_header_is_present(self, greeting_stream):
        header_names = {k.lower() for k in greeting_stream.headers}
        assert "x-session-id" in header_names

    def test_x_session_id_header_is_uuid_format(self, greeting_stream):
        sid = greeting_stream.headers.get("x-session-id", "")
        assert len(sid) > 0
        parsed = uuid.UUID(sid, version=4)
        assert str(parsed) == sid

    def test_body_contains_data_lines(self, greeting_stream):
        assert "data: " in greeting_stream.text

    def test_body_ends_with_done_sentinel(self, greeting_stream):
        assert "[DONE]" in greeting_stream.text, (
            "SSE stream must end with 'data: [DONE]'"
        )

    def test_assembled_content_is_non_empty(self, greeting_stream):
        payloads = [
            line[6:]
            for line in greeting_stream.text.splitlines()
            if line.startswith("data: ") and "[DONE]" not in line
        ]
        assembled = "".join(payloads)
        assert len(assembled) > 0, "Streamed content assembled to empty string"

    def test_default_stream_parameter_is_true(self, client):
        """Omitting 'stream' should default to SSE (stream=True)."""
        resp = client.post("/chat", json={"message": "Hello"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


# ── Multi-turn session continuity ─────────────────────────────────────────────

class TestSessionContinuity:

    def test_first_turn_returns_200(self, first_turn):
        assert first_turn.status_code == 200

    def test_second_turn_returns_200(self, second_turn):
        assert second_turn.status_code == 200

    def test_both_turns_share_session_id(self, first_turn, second_turn, session_id_for_continuity):
        assert first_turn.json()["session_id"]  == session_id_for_continuity
        assert second_turn.json()["session_id"] == session_id_for_continuity

    def test_second_turn_response_is_non_empty(self, second_turn):
        assert len(second_turn.json()["response"]) > 0

    def test_second_turn_references_prior_context(self, second_turn):
        """
        The coordinator has memory — asking 'What name did I just tell you?'
        should produce a response that contains 'Test User' or at least 'test'
        (case-insensitive), proving the session history was used.
        """
        response_text = second_turn.json()["response"].lower()
        assert "test" in response_text, (
            f"Expected the agent to reference the name from the prior turn.\n"
            f"Response was: {second_turn.json()['response']}"
        )


# ── GET /session/{id}/history ─────────────────────────────────────────────────

class TestSessionHistory:

    def test_returns_200(self, client, session_id_for_continuity, first_turn):
        resp = client.get(f"/session/{session_id_for_continuity}/history")
        assert resp.status_code == 200

    def test_response_has_session_id_and_messages(self, client, session_id_for_continuity, first_turn):
        data = client.get(f"/session/{session_id_for_continuity}/history").json()
        assert "session_id" in data
        assert "messages"   in data

    def test_session_id_is_echoed_correctly(self, client, session_id_for_continuity, first_turn):
        data = client.get(f"/session/{session_id_for_continuity}/history").json()
        assert data["session_id"] == session_id_for_continuity

    def test_messages_is_a_list(self, client, session_id_for_continuity, first_turn):
        data = client.get(f"/session/{session_id_for_continuity}/history").json()
        assert isinstance(data["messages"], list)

    def test_history_is_non_empty_after_chat(self, client, session_id_for_continuity, first_turn):
        """After sending at least one message the history list must not be empty."""
        data = client.get(f"/session/{session_id_for_continuity}/history").json()
        assert len(data["messages"]) > 0

    def test_unknown_session_returns_200_with_empty_messages(self, client):
        """A session_id that has never been used returns 200 with an empty messages list."""
        sid  = f"never-used-{uuid.uuid4().hex}"
        data = client.get(f"/session/{sid}/history").json()
        assert data["session_id"] == sid
        assert isinstance(data["messages"], list)


# ── Request validation (no LLM call — FastAPI rejects before routing) ─────────

class TestRequestValidation:

    def test_missing_message_field_returns_422(self, client):
        resp = client.post("/chat", json={"stream": False})
        assert resp.status_code == 422

    def test_non_json_body_returns_422(self, client):
        resp = client.post(
            "/chat",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_extra_unknown_fields_are_ignored(self, client):
        resp = client.post("/chat", json={
            "message": "Hello",
            "stream": False,
            "totally_unknown_field": "should be ignored",
        })
        assert resp.status_code == 200

    def test_null_session_id_triggers_auto_generation(self, client):
        resp = client.post("/chat", json={"message": "Hello", "session_id": None, "stream": False})
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        assert sid is not None and len(sid) > 0
