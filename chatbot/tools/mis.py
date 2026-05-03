"""
MIS tools: financial_period_resolver, get_company_trend,
get_mis_recent_summary, get_bu_breakdown, get_outlet_breakdown.

Queries: mis_monthly, mis_bu_monthly, mis_outlet_monthly.
"""
import json
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from chatbot.config import FY_START_MONTH
from chatbot.db import get_conn, get_cursor


def financial_period_resolver(period: str) -> str:
    """
    Convert a financial period string to an exact ISO date range.
    Call this before any date-filtered MIS query when the user provides a
    relative or fiscal period reference.

    Supported formats:
        'FY26'          → 2025-04-01 to 2026-03-31
        'FY25'          → 2024-04-01 to 2025-03-31
        'Q1_FY26'       → 2025-04-01 to 2025-06-30
        'Q2_FY26'       → 2025-07-01 to 2025-09-30
        'Q3_FY26'       → 2025-10-01 to 2025-12-31
        'Q4_FY26'       → 2026-01-01 to 2026-03-31
        'H1_FY26'       → 2025-04-01 to 2025-09-30
        'H2_FY26'       → 2025-10-01 to 2026-03-31
        'last_3_months' → rolling last 3 complete months
        'last_6_months' → rolling last 6 complete months
        'ytd'           → FY start to today
        'latest'        → most recent complete month

    Returns:
        JSON with 'start' and 'end' keys (ISO date strings, inclusive).
    """
    today = date.today()
    p = period.strip().upper()

    def _last_day(y: int, m: int) -> int:
        return (date(y, m % 12 + 1, 1) - timedelta(days=1)).day if m < 12 else 31

    # Explicit range: 'YYYY-MM-DD:YYYY-MM-DD'
    if ":" in p and len(p) == 21:
        parts = p.split(":")
        return json.dumps({"start": parts[0], "end": parts[1]})

    # Full fiscal year: FY26
    if p.startswith("FY") and "_" not in p and len(p) == 4:
        fy_year = int("20" + p[2:])
        start   = date(fy_year - 1, FY_START_MONTH, 1)
        end     = date(fy_year, FY_START_MONTH - 1, _last_day(fy_year, FY_START_MONTH - 1))
        return json.dumps({"start": str(start), "end": str(end)})

    # Quarter: Q2_FY26
    if p.startswith("Q") and "_FY" in p:
        q_num    = int(p[1])
        fy_year  = int("20" + p.split("_FY")[1])
        fy_start = date(fy_year - 1, FY_START_MONTH, 1)
        q_start  = fy_start + relativedelta(months=(q_num - 1) * 3)
        q_end    = q_start  + relativedelta(months=3) - timedelta(days=1)
        return json.dumps({"start": str(q_start), "end": str(q_end)})

    # Half-year: H1_FY26
    if p.startswith("H") and "_FY" in p:
        h_num    = int(p[1])
        fy_year  = int("20" + p.split("_FY")[1])
        fy_start = date(fy_year - 1, FY_START_MONTH, 1)
        h_start  = fy_start + relativedelta(months=(h_num - 1) * 6)
        h_end    = h_start  + relativedelta(months=6) - timedelta(days=1)
        return json.dumps({"start": str(h_start), "end": str(h_end)})

    if p in ("LAST_3_MONTHS", "LAST3MONTHS"):
        end   = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1) - relativedelta(months=2)
        return json.dumps({"start": str(start), "end": str(end)})

    if p in ("LAST_6_MONTHS", "LAST6MONTHS"):
        end   = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1) - relativedelta(months=5)
        return json.dumps({"start": str(start), "end": str(end)})

    if p == "YTD":
        fy_start = (
            date(today.year, FY_START_MONTH, 1)
            if today.month >= FY_START_MONTH
            else date(today.year - 1, FY_START_MONTH, 1)
        )
        return json.dumps({"start": str(fy_start), "end": str(today)})

    if p in ("LATEST", "LAST_MONTH"):
        first_of_this = today.replace(day=1)
        end   = first_of_this - timedelta(days=1)
        start = end.replace(day=1)
        return json.dumps({"start": str(start), "end": str(end)})

    # Default: current FY
    fy_year = today.year + (1 if today.month >= FY_START_MONTH else 0)
    start   = date(fy_year - 1, FY_START_MONTH, 1)
    end     = date(fy_year, FY_START_MONTH - 1, _last_day(fy_year, FY_START_MONTH - 1))
    return json.dumps({"start": str(start), "end": str(end)})


def get_company_trend(
    company_id: str,
    period: str = "FY26",
    geography: str = "consolidated",
    granularity: str = "monthly",
) -> str:
    """
    Return time-series financial trend data for a MIS company with MoM
    change annotations and summary statistics.

    Args:
        company_id: 'company_01' or 'company_02'.
        period: Period string — 'FY26', 'Q1_FY26', 'last_6_months', 'ytd', etc.
                Call financial_period_resolver first when unsure.
        geography: 'consolidated' (default) | 'country_a' (India) | 'city_z' (Dubai).
        granularity: 'monthly' (default) | 'quarterly'.

    Returns:
        JSON with: currency, summary (stats), trend (array of period rows with
        MoM change fields).
    """
    period_range = json.loads(financial_period_resolver(period))
    start_date   = period_range["start"]
    end_date     = period_range["end"]

    with get_conn() as conn, get_cursor(conn) as cur:
        if granularity == "quarterly":
            cur.execute("""
                SELECT
                    DATE_TRUNC('quarter', month_date)::DATE AS period_date,
                    TO_CHAR(DATE_TRUNC('quarter', month_date),'YYYY "Q"Q') AS period_label,
                    ROUND(SUM(total_income_lacs),2)          AS revenue,
                    ROUND(SUM(ebitda_lacs),2)                AS ebitda,
                    ROUND(AVG(ebitda_pct)*100,2)             AS ebitda_pct,
                    ROUND(SUM(gross_margin_lacs),2)          AS gross_margin,
                    ROUND(AVG(gross_margin_pct)*100,2)       AS gross_margin_pct,
                    ROUND(SUM(cogs_lacs),2)                  AS cogs,
                    ROUND(SUM(total_operating_costs_lacs),2) AS operating_costs,
                    ROUND(SUM(manpower_cost_lacs),2)         AS manpower_cost,
                    ROUND(SUM(rent_lacs),2)                  AS rent,
                    ROUND(SUM(marketing_lacs),2)             AS marketing
                FROM mis_monthly
                WHERE company_id=%s AND geography=%s
                  AND month_date BETWEEN %s AND %s
                GROUP BY DATE_TRUNC('quarter', month_date)
                ORDER BY period_date
            """, (company_id, geography, start_date, end_date))
        else:
            cur.execute("""
                SELECT
                    month_date                                AS period_date,
                    TO_CHAR(month_date,'Mon-YY')             AS period_label,
                    ROUND(total_income_lacs,2)               AS revenue,
                    ROUND(ebitda_lacs,2)                     AS ebitda,
                    ROUND(ebitda_pct*100,2)                  AS ebitda_pct,
                    ROUND(gross_margin_lacs,2)               AS gross_margin,
                    ROUND(gross_margin_pct*100,2)            AS gross_margin_pct,
                    ROUND(cogs_lacs,2)                       AS cogs,
                    ROUND(total_operating_costs_lacs,2)      AS operating_costs,
                    ROUND(manpower_cost_lacs,2)              AS manpower_cost,
                    ROUND(rent_lacs,2)                       AS rent,
                    ROUND(marketing_lacs,2)                  AS marketing
                FROM mis_monthly
                WHERE company_id=%s AND geography=%s
                  AND month_date BETWEEN %s AND %s
                ORDER BY month_date
            """, (company_id, geography, start_date, end_date))

        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return json.dumps({
            "error": f"No MIS data for {company_id} in {period} ({start_date}–{end_date})"
        })

    # Annotate MoM changes
    for i, row in enumerate(rows):
        row["mom_revenue_change_pct"] = None
        row["mom_ebitda_change_lacs"] = None
        if i > 0:
            prev = rows[i - 1]
            if prev["revenue"] and float(prev["revenue"]) != 0:
                row["mom_revenue_change_pct"] = round(
                    (float(row["revenue"]) - float(prev["revenue"])) / abs(float(prev["revenue"])) * 100, 2
                )
            if row["ebitda"] is not None and prev["ebitda"] is not None:
                row["mom_ebitda_change_lacs"] = round(
                    float(row["ebitda"]) - float(prev["ebitda"]), 2
                )
        # Normalise Decimals for JSON
        for k, v in row.items():
            if hasattr(v, "__float__"):
                row[k] = float(v)

    revenues = [r["revenue"] for r in rows if r["revenue"] is not None]
    ebitdas  = [r["ebitda"]  for r in rows if r["ebitda"]  is not None]

    ebitda_trend = "insufficient_data"
    if len(ebitdas) >= 3:
        last3 = ebitdas[-3:]
        if all(last3[i] > last3[i - 1] for i in range(1, 3)):
            ebitda_trend = "improving"
        elif all(last3[i] < last3[i - 1] for i in range(1, 3)):
            ebitda_trend = "deteriorating"
        else:
            ebitda_trend = "mixed"

    summary = {
        "company_id": company_id,
        "period": period,
        "geography": geography,
        "data_points": len(rows),
        "ebitda_trend": ebitda_trend,
        "latest_revenue_lacs": revenues[-1] if revenues else None,
        "latest_ebitda_lacs":  ebitdas[-1]  if ebitdas  else None,
        "revenue_growth_pct": (
            round((revenues[-1] - revenues[0]) / abs(revenues[0]) * 100, 2)
            if len(revenues) >= 2 and revenues[0]
            else None
        ),
    }

    return json.dumps({"currency": "INR_Lacs", "summary": summary, "trend": rows}, default=str)


def get_mis_recent_summary(company_id: str) -> str:
    """
    Generate a structured MoM comparison for a company: latest available
    month vs the prior month. Covers all consolidated P&L metrics.

    Args:
        company_id: 'company_01' or 'company_02'.

    Returns:
        JSON with: latest_month, prior_month, metric_changes (per-metric dict
        with current, prior, change_abs, change_pct, direction), headline_flags,
        overall_direction ('improving' | 'mixed' | 'deteriorating').
    """
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT TO_CHAR(month_date,'Mon-YY')        AS month_label,
                   ROUND(total_income_lacs,2)           AS revenue,
                   ROUND(cogs_lacs,2)                   AS cogs,
                   ROUND(gross_margin_lacs,2)           AS gross_margin,
                   ROUND(gross_margin_pct*100,2)        AS gross_margin_pct,
                   ROUND(total_operating_costs_lacs,2)  AS operating_costs,
                   ROUND(manpower_cost_lacs,2)          AS manpower_cost,
                   ROUND(rent_lacs,2)                   AS rent,
                   ROUND(marketing_lacs,2)              AS marketing,
                   ROUND(ebitda_lacs,2)                 AS ebitda,
                   ROUND(ebitda_pct*100,2)              AS ebitda_pct
            FROM mis_monthly
            WHERE company_id=%s AND geography='consolidated'
            ORDER BY month_date DESC LIMIT 2
        """, (company_id,))
        rows = cur.fetchall()

    if len(rows) < 2:
        return json.dumps({"error": f"Need at least 2 months of consolidated data for {company_id}."})

    latest, prior = dict(rows[0]), dict(rows[1])
    cost_metrics  = {"cogs", "operating_costs", "manpower_cost", "rent", "marketing"}
    metric_keys   = [
        "revenue", "cogs", "gross_margin", "gross_margin_pct",
        "operating_costs", "manpower_cost", "rent", "marketing",
        "ebitda", "ebitda_pct",
    ]

    changes: dict = {}
    for m in metric_keys:
        c_val, p_val = latest.get(m), prior.get(m)
        if c_val is None or p_val is None or float(p_val) == 0:
            changes[m] = {
                "current": float(c_val) if c_val else None,
                "prior":   float(p_val) if p_val else None,
                "change_abs": None, "change_pct": None, "direction": "unknown",
            }
            continue
        c, p       = float(c_val), float(p_val)
        chg_abs    = round(c - p, 2)
        chg_pct    = round((c - p) / abs(p) * 100, 2)
        direction  = (
            ("worsened" if chg_abs > 0 else "improved" if chg_abs < 0 else "stable")
            if m in cost_metrics
            else ("improved" if chg_abs > 0 else "worsened" if chg_abs < 0 else "stable")
        )
        changes[m] = {"current": c, "prior": p,
                      "change_abs": chg_abs, "change_pct": chg_pct, "direction": direction}

    flags = []
    if changes.get("revenue", {}).get("direction") == "worsened":
        flags.append(f"Revenue declined {abs(changes['revenue']['change_pct'])}% MoM")
    if changes.get("ebitda", {}).get("direction") == "worsened":
        flags.append(f"EBITDA worsened by ₹{abs(changes['ebitda']['change_abs'])} Lacs")
    if changes.get("gross_margin_pct", {}).get("direction") == "worsened":
        flags.append(f"Gross margin compressed {abs(changes['gross_margin_pct']['change_abs'])}pp")
    if not flags:
        flags.append("No major deterioration flags — metrics stable or improving.")

    ebitda_dir  = changes.get("ebitda",  {}).get("direction", "unknown")
    revenue_dir = changes.get("revenue", {}).get("direction", "unknown")
    overall = (
        "improving"    if ebitda_dir == "improved"  and revenue_dir == "improved"  else
        "deteriorating" if ebitda_dir == "worsened" and revenue_dir == "worsened"  else
        "mixed"
    )

    return json.dumps({
        "company_id": company_id,
        "latest_month": latest["month_label"],
        "prior_month":  prior["month_label"],
        "overall_direction": overall,
        "headline_flags": flags,
        "metric_changes": changes,
    }, default=str)


def get_bu_breakdown(company_id: str, period: str = "latest") -> str:
    """
    Return BU-level revenue, EBITDA, and channel breakdown for a company.
    Most relevant for Company_02 (up to 12 BUs). Company_01 has 2 BUs.

    Args:
        company_id: 'company_01' or 'company_02'.
        period: Period string — 'latest', 'FY26', 'Q1_FY26', etc.

    Returns:
        JSON with company_id, period, and bu_data (list of BU rows).
    """
    period_range = json.loads(financial_period_resolver(period))
    start_date   = period_range["start"]
    end_date     = period_range["end"]

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT bu_id,
                   TO_CHAR(month_date,'Mon-YY')            AS month,
                   ROUND(revenue_lacs,2)                   AS revenue_lacs,
                   ROUND(ebitda_lacs,2)                    AS ebitda_lacs,
                   ROUND(gross_margin_pct*100,2)           AS gross_margin_pct,
                   ROUND(channel_dine_in_lacs,2)           AS dine_in_lacs,
                   ROUND(channel_aggregator_a_lacs,2)      AS aggregator_a_lacs,
                   ROUND(channel_aggregator_b_lacs,2)      AS aggregator_b_lacs,
                   ROUND(channel_catering_lacs,2)          AS catering_lacs,
                   ROUND(channel_franchise_lacs,2)         AS franchise_lacs
            FROM mis_bu_monthly
            WHERE company_id=%s AND month_date BETWEEN %s AND %s
            ORDER BY bu_id, month_date
        """, (company_id, start_date, end_date))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return json.dumps({"error": f"No BU data for {company_id} in {period}"})

    return json.dumps(
        {"company_id": company_id, "period": period, "bu_data": rows},
        default=str,
    )


def get_outlet_breakdown(period: str = "latest") -> str:
    """
    Return outlet-level P&L for Company_01 (the only company with outlet data).

    Args:
        period: Period string — 'latest', 'FY26', 'Q1_FY26', etc.

    Returns:
        JSON with company_id, period, and outlet_data (list of outlet rows).
    """
    period_range = json.loads(financial_period_resolver(period))
    start_date   = period_range["start"]
    end_date     = period_range["end"]

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT outlet_id, city, bu_id,
                   TO_CHAR(month_date,'Mon-YY')            AS month,
                   ROUND(revenue_lacs,2)                   AS revenue_lacs,
                   ROUND(operational_profit_lacs,2)        AS operational_profit_lacs,
                   ROUND(operational_profit_pct*100,2)     AS operational_profit_pct,
                   sales_to_rent_ratio, covers, area_sqft
            FROM mis_outlet_monthly
            WHERE company_id='company_01' AND month_date BETWEEN %s AND %s
            ORDER BY outlet_id, month_date
        """, (start_date, end_date))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return json.dumps({"error": f"No outlet data for Company_01 in {period}"})

    return json.dumps(
        {"company_id": "company_01", "period": period, "outlet_data": rows},
        default=str,
    )
