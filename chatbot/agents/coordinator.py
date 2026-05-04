"""
Coordinator — manages session memory, routes to the Analyst, synthesises responses.
"""
from agno.team import Team
from agno.models.azure import AzureOpenAI
from agno.tools.reasoning import ReasoningTools
from agno.db.postgres import PostgresDb

from chatbot.config import (
    DB_URL_SYNC,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
    AGENT_SESSION_TABLE,
    AGENT_NUM_HISTORY_RUNS,
)
from chatbot.prompts import COORDINATOR_PROMPT
from chatbot.agents.analyst import create_analyst


def _make_model() -> AzureOpenAI:
    return AzureOpenAI(
        id=AZURE_OPENAI_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        timeout=300,        # 5 min — prevents Azure dropping long-running streams
        max_retries=2,
    )


def create_coordinator(session_id: str = None) -> Team:
    """
    Create the full coordinator team.

    The coordinator:
    - Holds all session history (single memory store — no per-agent fragmentation)
    - Routes data questions to the Analyst
    - Handles greetings and clarifications itself
    - Synthesises multi-part answers into one coherent response

    Args:
        session_id: UUID string. Pass the same ID across turns to maintain
                    conversation continuity. A new session_id starts a fresh
                    conversation.
    """
    db = PostgresDb(
        session_table=f"{AGENT_SESSION_TABLE}_coordinator",
        db_url=DB_URL_SYNC,
    )

    return Team(
        name="NKSquared Investment Intelligence",
        model=_make_model(),
        members=[create_analyst()],

        tools=[],
        instructions=[COORDINATOR_PROMPT],

        db=db,
        session_id=session_id,
        enable_agentic_memory=True,
        add_history_to_context=True,
        num_history_runs=AGENT_NUM_HISTORY_RUNS,
        read_chat_history=True,
        add_datetime_to_context=True,

        show_members_responses=False,   # only show the synthesised coordinator response
        markdown=True,
        stream=True,
    )
