"""Dashboard Agent factory."""
from typing import List

from agno.agent import Agent
from agno.models.azure import AzureOpenAI

from dashboard.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)
from dashboard.prompts import get_dashboard_prompt
from dashboard.tools.data import (
    resolve_period,
    get_portfolio_summary,
    get_portfolio_aggregates,
    get_company_detail,
    get_transaction_timeline,
    get_cap_table_snapshot,
    get_valuation_history,
    get_entity_breakdown,
    calculate_irr,
    check_portfolio_alerts,
    get_company_trend,
    get_mis_recent_summary,
    get_cost_breakdown,
    get_bu_breakdown,
    get_channel_breakdown,
    get_outlet_breakdown,
    get_outlet_profitability,
    get_mis_submission_status,
    get_mis_anomaly_summary,
    run_query,
    convert_forex,
    compute_executive_summary,
)
from dashboard.tools.charts import (
    create_bar_chart,
    create_line_chart,
    create_pie_chart,
    create_kpi_cards,
    create_table_image,
    create_waterfall_chart,
    create_combo_chart,
    create_scatter_chart,
    create_stacked_area_chart,
    create_bullet_chart,
    create_heatmap,
    create_treemap,
)
from dashboard.tools.assembly import compile_dashboard


def create_dashboard_agent(dashboard_id: str, user_id: int) -> Agent:
    """
    Create a fresh, stateless Dashboard Agent for one PDF generation run.

    No session history, no caching — each generate request creates a new agent.
    The dashboard_id and user_id are baked into compile_dashboard via a closure
    so the agent's tool calls are scoped to this specific job.
    """

    def _compile_dashboard(
        title: str,
        subtitle: str,
        sections: List[dict],
        period_label: str = "",
        generated_by: str = "NKSquared AI",
    ) -> dict:
        """
        Compile all sections into a PDF report and save it.
        Call this EXACTLY ONCE after all data has been fetched and all charts generated.

        Args:
            title: Dashboard title (e.g. "Portfolio Overview FY26").
            subtitle: Subtitle line (e.g. "Portfolio Overview — FY26").
            sections: Ordered list of section descriptors.
            period_label: Human-readable period string for the header.
            generated_by: Attribution string for the footer.

        Returns:
            {status, download_url, page_count}
        """
        return compile_dashboard(
            dashboard_id=dashboard_id,
            title=title,
            subtitle=subtitle,
            sections=sections,
            user_id=user_id,
            period_label=period_label,
            generated_by=generated_by,
        )

    return Agent(
        name="DashboardAgent",
        model=AzureOpenAI(
            id=AZURE_OPENAI_DEPLOYMENT,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            timeout=180,
            max_retries=2,
        ),
        tools=[
            # Data tools (21)
            resolve_period,
            get_portfolio_summary,
            get_portfolio_aggregates,
            get_company_detail,
            get_transaction_timeline,
            get_cap_table_snapshot,
            get_valuation_history,
            get_entity_breakdown,
            calculate_irr,
            check_portfolio_alerts,
            get_company_trend,
            get_mis_recent_summary,
            get_cost_breakdown,
            get_bu_breakdown,
            get_channel_breakdown,
            get_outlet_breakdown,
            get_outlet_profitability,
            get_mis_submission_status,
            get_mis_anomaly_summary,
            run_query,
            convert_forex,
            compute_executive_summary,
            # Chart tools (12)
            create_bar_chart,
            create_line_chart,
            create_pie_chart,
            create_kpi_cards,
            create_table_image,
            create_waterfall_chart,
            create_combo_chart,
            create_scatter_chart,
            create_stacked_area_chart,
            create_bullet_chart,
            create_heatmap,
            create_treemap,
            # Assembly (closure — baked with dashboard_id + user_id)
            _compile_dashboard,
        ],
        instructions=[
            get_dashboard_prompt(),
            f"SESSION dashboard_id: {dashboard_id} — use this exact string as the dashboard_id argument in EVERY chart tool call (create_kpi_cards, create_bar_chart, create_pie_chart, etc.).",
        ],
        markdown=True,
        add_history_to_context=False,  # stateless single-shot run
    )
