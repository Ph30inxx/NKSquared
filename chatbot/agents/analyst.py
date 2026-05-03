"""
NKSquared Analyst Agent — single agent with all analytical and SQL tools.
Handles every data question: portfolio, MIS, and cross-cutting analysis.
"""
from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agno.tools.sql import SQLTools
from agno.tools.reasoning import ReasoningTools
from agno.db.postgres import PostgresDb

from chatbot.config import (
    DB_URL_SYNC,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
    AGENT_SESSION_TABLE,
)
from chatbot.prompts import get_analyst_prompt
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


def _make_model() -> AzureOpenAI:
    return AzureOpenAI(
        id=AZURE_OPENAI_DEPLOYMENT,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def create_analyst() -> Agent:
    """
    Create the NKSquared Analyst agent.

    Tool stack (in priority order as guided by the system prompt):
      1. find_similar_query    — check knowledge base first
      2. Structured tools      — get_portfolio_summary, get_company_trend, etc.
      3. execute_safe_query    — row-capped, table-allowlisted ad-hoc SQL
      4. SQLTools              — full SQL flexibility for complex edge cases
      5. ReasoningTools        — multi-step planning before complex queries
      6. save_validated_query  — persist confirmed correct answers

    The analyst is stateless (no history). The Coordinator owns session context
    and passes it through the message.
    """
    db = PostgresDb(
        session_table=f"{AGENT_SESSION_TABLE}_analyst",
        db_url=DB_URL_SYNC,
    )

    return Agent(
        name="NKSquared Analyst",
        id="nksquared_analyst",
        role="Investment intelligence analyst for NKSquared",
        model=_make_model(),

        tools=[
            # Step 0: planning
            ReasoningTools(add_instructions=True),

            # Step 1: knowledge base lookup
            find_similar_query,
            save_validated_query,

            # Step 2: portfolio structured tools
            get_portfolio_summary,
            get_company_portfolio_detail,
            calculate_irr,
            check_portfolio_alerts,

            # Step 3: MIS structured tools
            financial_period_resolver,
            get_company_trend,
            get_mis_recent_summary,
            get_bu_breakdown,
            get_outlet_breakdown,

            # Step 4: shared utilities
            forex_converter,

            # Step 5: ad-hoc SQL (row-capped, allowlisted)
            execute_safe_query,

            # Step 6: full SQL for complex joins / edge cases
            SQLTools(db_url=DB_URL_SYNC),
        ],

        instructions=get_analyst_prompt(),

        db=db,
        add_history_to_context=False,   # coordinator passes context in the message
        add_datetime_to_context=True,
        markdown=True,
    )
