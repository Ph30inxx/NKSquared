"""
NKSquared Intelligence Agent — unified single agent replacing the
Coordinator + Analyst team architecture for lower latency.

Eliminates 2 unnecessary LLM round-trips (routing + synthesis) by
merging all capabilities into a single agent with direct tool access.
"""
from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agno.tools.sql import SQLTools
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
from chatbot.prompts import get_intelligence_prompt
from chatbot.tools.portfolio import (
    get_portfolio_summary,
    get_company_portfolio_detail,
    calculate_irr,
    check_portfolio_alerts,
)
from chatbot.tools.mis import (
    financial_period_resolver,
    get_company_trend,
    get_mis_recent_summary,
    get_bu_breakdown,
    get_outlet_breakdown,
)
from chatbot.tools.shared import (
    forex_converter,
    execute_safe_query,
    find_similar_query,
    save_validated_query,
)
from chatbot.tools.write import (
    log_transaction,
    add_valuation,
    update_company,
    upsert_forex_rate,
    send_mis_reminder,
    create_company,
    manage_reminder_schedule,
    correct_transaction,
    correct_mis_metric,
    deactivate_company,
    get_reminder_logs,
)

# ── Tool sets ─────────────────────────────────────────────────────────────────

_READ_TOOLS = [
    # Knowledge base lookup
    find_similar_query,
    save_validated_query,
    # Portfolio structured tools
    get_portfolio_summary,
    get_company_portfolio_detail,
    calculate_irr,
    check_portfolio_alerts,
    # MIS structured tools
    financial_period_resolver,
    get_company_trend,
    get_mis_recent_summary,
    get_bu_breakdown,
    get_outlet_breakdown,
    # Reminder history
    get_reminder_logs,
    # Shared utilities
    forex_converter,
    # Ad-hoc SQL (row-capped, allowlisted)
    execute_safe_query,
]

_WRITE_TOOLS = [
    log_transaction,
    add_valuation,
    update_company,
    upsert_forex_rate,
    send_mis_reminder,
    create_company,
    manage_reminder_schedule,
    correct_transaction,
    correct_mis_metric,
    deactivate_company,
]

# Keywords that indicate write intent
WRITE_KEYWORDS = frozenset({
    "log", "add", "update", "create", "delete", "set", "change",
    "correct", "fix", "send", "deactivate", "archive", "mark",
    "record", "enter", "submit", "remove", "disable", "enable",
})


# ── Shared instances ──────────────────────────────────────────────────────────
# Instantiated once at module load to reuse the same SQLAlchemy engine
# and connection pool across all requests/agent instances.
_DB = PostgresDb(
    session_table=f"{AGENT_SESSION_TABLE}_intelligence",
    db_url=DB_URL_SYNC,
)

_SQL_TOOLS = SQLTools(db_url=DB_URL_SYNC)


def needs_write_tools(message: str) -> bool:
    """Quick heuristic check for write intent in a user message."""
    words = set(message.lower().split())
    return bool(words & WRITE_KEYWORDS)


# ── Model factory ─────────────────────────────────────────────────────────────

def _make_model() -> AzureOpenAI:
    return AzureOpenAI(
        id=AZURE_OPENAI_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        timeout=120,
        max_retries=2,
    )


# ── Agent factory ─────────────────────────────────────────────────────────────

def create_intelligence_agent(
    session_id: str = None,
    include_write_tools: bool = False,
    voice_mode: bool = False,
) -> Agent:
    """
    Create the unified NKSquared Intelligence agent.

    Replaces the previous Coordinator + Analyst Team architecture.
    A single agent with all tools eliminates 2 LLM round-trips per query
    (routing + synthesis) while keeping the same capabilities.

    Args:
        session_id: UUID for conversation continuity.
        include_write_tools: If True, register write tools alongside read tools.
            Reduces tool token overhead by ~50% on read-only queries.
    """
    tools = list(_READ_TOOLS)
    # Full SQL for complex joins / edge cases
    tools.append(_SQL_TOOLS)
    if include_write_tools:
        tools.extend(_WRITE_TOOLS)

    return Agent(
        name="NKSquared Intelligence",
        model=_make_model(),
        tools=tools,

        instructions=[get_intelligence_prompt(
            include_write_rules=include_write_tools,
            voice_mode=voice_mode,
        )],

        db=_DB,
        session_id=session_id,
        add_history_to_context=True,
        num_history_runs=AGENT_NUM_HISTORY_RUNS,
        add_datetime_to_context=True,

        markdown=not voice_mode,
        stream=True,
    )
