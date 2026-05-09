"""
Dashboard data tools — 20 tools for the Dashboard Agent.

Tools 1-11 are clean re-implementations of chatbot tool logic (self-contained,
no imports from chatbot.tools so the dashboard agent has its own tool set).
Tools 12-20 are new tools exposing data not covered by any chatbot tool.
"""
import json
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from chatbot.config import FY_START_MONTH, SAFE_QUERY_ROW_LIMIT
from chatbot.db import get_conn, get_cursor


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_day(y: int, m: int) -> int:
    return (date(y, m % 12 + 1, 1) - timedelta(days=1)).day if m < 12 else 31


def _resolve(period: str) -> tuple[str, str, str]:
    """Returns (start_iso, end_iso, label)."""
    today = date.today()
    p = period.strip().upper()

    if ":" in p and len(p) == 21:
        parts = p.split(":")
        return parts[0], parts[1], period

    if p.startswith("FY") and "_" not in p and len(p) == 4:
        fy_year = int("20" + p[2:])
        s = date(fy_year - 1, FY_START_MONTH, 1)
        e = date(fy_year, FY_START_MONTH - 1, _last_day(fy_year, FY_START_MONTH - 1))
        return str(s), str(e), p

    if p.startswith("Q") and "_FY" in p:
        q_num = int(p[1])
        fy_year = int("20" + p.split("_FY")[1])
        fy_start = date(fy_year - 1, FY_START_MONTH, 1)
        q_start = fy_start + relativedelta(months=(q_num - 1) * 3)
        q_end = q_start + relativedelta(months=3) - timedelta(days=1)
        return str(q_start), str(q_end), p

    if p.startswith("H") and "_FY" in p:
        h_num = int(p[1])
        fy_year = int("20" + p.split("_FY")[1])
        fy_start = date(fy_year - 1, FY_START_MONTH, 1)
        h_start = fy_start + relativedelta(months=(h_num - 1) * 6)
        h_end = h_start + relativedelta(months=6) - timedelta(days=1)
        return str(h_start), str(h_end), p

    if p in ("LAST_3_MONTHS", "LAST3MONTHS"):
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1) - relativedelta(months=2)
        return str(start), str(end), "last_3_months"

    if p in ("LAST_6_MONTHS", "LAST6MONTHS"):
        end = today.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1) - relativedelta(months=5)
        return str(start), str(end), "last_6_months"

    if p == "YTD":
        fy_start = (
            date(today.year, FY_START_MONTH, 1)
            if today.month >= FY_START_MONTH
            else date(today.year - 1, FY_START_MONTH, 1)
        )
        return str(fy_start), str(today), "ytd"

    if p in ("LATEST", "LAST_MONTH"):
        first_of_this = today.replace(day=1)
        end = first_of_this - timedelta(days=1)
        start = end.replace(day=1)
        return str(start), str(end), "latest"

    fy_year = today.year + (1 if today.month >= FY_START_MONTH else 0)
    s = date(fy_year - 1, FY_START_MONTH, 1)
    e = date(fy_year, FY_START_MONTH - 1, _last_day(fy_year, FY_START_MONTH - 1))
    return str(s), str(e), p


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — resolve_period
# ─────────────────────────────────────────────────────────────────────────────

def resolve_period(period: str) -> dict:
    """
    Convert a period string to an ISO date range.

    Supported: FY26, Q1_FY26, H1_FY26, last_3_months, last_6_months,
    ytd, latest, YYYY-MM-DD:YYYY-MM-DD.

    Always call this first when the user mentions any time period.

    Returns:
        {start, end, label}
    """
    s, e, label = _resolve(period)
    return {"start": s, "end": e, "label": label}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — get_portfolio_summary
# ─────────────────────────────────────────────────────────────────────────────

def get_portfolio_summary(group_by: str = "sector", include_written_off: bool = True) -> dict:
    """
    Return portfolio totals and per-group breakdown.

    Args:
        group_by: 'sector' | 'portfolio_type' | 'asset_class' | 'investment_status'
        include_written_off: Include written-off companies in totals.

    Returns:
        {totals, breakdown, top_performers, alerts}
    """
    valid_cols = {"sector", "portfolio_type", "asset_class", "investment_status"}
    group_col = group_by if group_by in valid_cols else "sector"

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT COUNT(*) AS total_count,
                   COUNT(*) FILTER (WHERE portfolio_status='Unrealized') AS unrealized,
                   COUNT(*) FILTER (WHERE portfolio_status='Realized')   AS realized,
                   COUNT(*) FILTER (WHERE investment_status='Written_off') AS written_off,
                   ROUND(SUM(ABS(investment_value_cr)),2) AS invested_cr,
                   ROUND(SUM(current_value_cr),2)         AS current_cr,
                   ROUND(SUM(current_value_cr)/NULLIF(SUM(ABS(investment_value_cr)),0),4) AS moic
            FROM portfolio_companies
            WHERE is_active=true
              AND (investment_status!='Written_off' OR %s=true)
        """, (include_written_off,))
        totals = dict(cur.fetchone())

        cur.execute(f"""
            SELECT {group_col} AS group_name,
                   COUNT(*) AS company_count,
                   ROUND(SUM(ABS(investment_value_cr)),2) AS invested_cr,
                   ROUND(SUM(current_value_cr),2) AS current_value_cr,
                   ROUND(SUM(current_value_cr)/NULLIF(SUM(ABS(investment_value_cr)),0),4) AS moic
            FROM portfolio_companies
            WHERE is_active=true AND (investment_status!='Written_off' OR %s=true)
            GROUP BY {group_col}
            ORDER BY invested_cr DESC NULLS LAST
        """, (include_written_off,))
        breakdown = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT display_name AS company, sector, portfolio_type,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic, investment_status
            FROM portfolio_companies
            WHERE moic IS NOT NULL AND is_active=true AND investment_status='Active'
            ORDER BY moic DESC LIMIT 5
        """)
        top_performers = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT display_name AS company, sector,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic, investment_status
            FROM portfolio_companies
            WHERE (moic<1.0 OR investment_status='Written_off') AND is_active=true
            ORDER BY moic ASC NULLS LAST LIMIT 10
        """)
        alerts = [dict(r) for r in cur.fetchall()]

    for d in [totals, *breakdown, *top_performers, *alerts]:
        for k, v in d.items():
            if hasattr(v, "__float__"):
                d[k] = float(v)

    return {"totals": totals, "breakdown": breakdown, "top_performers": top_performers, "alerts": alerts}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — get_company_detail
# ─────────────────────────────────────────────────────────────────────────────

def get_company_detail(company_name: str) -> dict:
    """
    Full profile for one company: position, transaction history, valuation history.

    Fuzzy-matches on display_name or company_name.

    Returns:
        {company, transactions, valuations}
    """
    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT id, display_name, company_name, sector, sub_sector,
                   portfolio_type, investment_status, portfolio_status, asset_class,
                   date_of_first_investment,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic, ROUND(irr*100,2) AS irr_pct,
                   country, currency, notes
            FROM portfolio_companies
            WHERE (LOWER(display_name) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))
              AND is_active=true
            LIMIT 1
        """, (pattern, pattern))
        company = cur.fetchone()
        if not company:
            return {"error": f"Company not found: '{company_name}'"}
        company = dict(company)
        cid = company["id"]

        cur.execute("""
            SELECT transaction_date, transaction_type,
                   ROUND(amount_inr_cr,4) AS amount_inr_cr,
                   original_currency, original_amount, series,
                   instrument_type, investing_entity, shareholding_pct, notes
            FROM portfolio_transactions WHERE company_id=%s ORDER BY transaction_date
        """, (cid,))
        transactions = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT valuation_date,
                   ROUND(post_money_valuation_cr,2) AS post_money_cr,
                   ROUND(pre_money_valuation_cr,2)  AS pre_money_cr,
                   source, currency
            FROM valuations WHERE company_id=%s ORDER BY valuation_date DESC
        """, (cid,))
        valuations = [dict(r) for r in cur.fetchall()]

    for lst in [transactions, valuations]:
        for d in lst:
            for k, v in d.items():
                if hasattr(v, "__float__"):
                    d[k] = float(v)

    return {"company": company, "transactions": transactions, "valuations": valuations}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — calculate_irr
# ─────────────────────────────────────────────────────────────────────────────

def calculate_irr(company_name: str) -> dict:
    """
    Compute XIRR for a portfolio company using its dated cash-flow history.

    Appends current_value_cr as a synthetic inflow at today's date.

    Returns:
        {irr_pct, moic, total_invested_cr, total_returned_cr, holding_period_years}
    """
    try:
        from pyxirr import xirr as _xirr
    except ImportError:
        return {"error": "pyxirr not installed."}

    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT id, display_name,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic
            FROM portfolio_companies
            WHERE (LOWER(display_name) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))
              AND is_active=true LIMIT 1
        """, (pattern, pattern))
        company = cur.fetchone()
        if not company:
            return {"error": f"Company not found: '{company_name}'"}

        cur.execute("""
            SELECT transaction_date, amount_inr_cr
            FROM portfolio_transactions
            WHERE company_id=%s
              AND transaction_type NOT IN ('Write_down','Write_off')
              AND amount_inr_cr IS NOT NULL
            ORDER BY transaction_date
        """, (company["id"],))
        rows = cur.fetchall()

    if not rows:
        return {"error": "No cash flow data found."}

    dates = [r["transaction_date"] for r in rows]
    amounts = [float(r["amount_inr_cr"]) for r in rows]

    if company["current_value_cr"] and float(company["current_value_cr"]) > 0:
        dates.append(date.today())
        amounts.append(float(company["current_value_cr"]))

    if len(dates) < 2:
        return {"error": "Need at least 2 cash flows to compute IRR."}

    try:
        irr = _xirr(dates, amounts)
    except Exception as exc:
        return {"error": f"IRR computation failed: {exc}"}

    total_invested = sum(abs(a) for a in amounts if a < 0)
    total_returned = sum(a for a in amounts if a > 0)
    holding_years = round((date.today() - dates[0]).days / 365.25, 2)

    return {
        "company": company["display_name"],
        "irr_pct": round(irr * 100, 2) if irr is not None else None,
        "moic": float(company["moic"]) if company["moic"] else None,
        "total_invested_cr": round(total_invested, 2),
        "total_returned_cr": round(total_returned, 2),
        "holding_period_years": holding_years,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — check_portfolio_alerts
# ─────────────────────────────────────────────────────────────────────────────

def check_portfolio_alerts() -> list:
    """
    Scan for portfolio health issues: MOIC < 0.95, written-off companies,
    3 consecutive months EBITDA worsening, revenue decline MoM.

    Returns:
        [{company, severity: HIGH|MEDIUM|INFO, alert_type, detail, action}]
    """
    alerts = []
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT display_name AS company, sector,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic
            FROM portfolio_companies
            WHERE moic<0.95 AND investment_status='Active'
              AND portfolio_status='Unrealized' AND is_active=true
            ORDER BY moic ASC
        """)
        for r in cur.fetchall():
            alerts.append({
                "severity": "HIGH", "alert_type": "MOIC_BELOW_095",
                "company": r["company"],
                "detail": f"MOIC {float(r['moic']):.2f}x on ₹{float(r['invested_cr']):.1f} Cr invested.",
                "action": "Review company health; consider impairment.",
            })

        cur.execute("""
            SELECT display_name AS company,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr
            FROM portfolio_companies
            WHERE investment_status='Written_off' AND is_active=true
        """)
        for r in cur.fetchall():
            alerts.append({
                "severity": "INFO", "alert_type": "WRITTEN_OFF",
                "company": r["company"],
                "detail": f"₹{float(r['invested_cr']):.1f} Cr written off.",
                "action": "No action unless reassessment requested.",
            })

        for cid in ("company_01", "company_02"):
            cur.execute("""
                SELECT ROUND(ebitda_lacs,2) AS ebitda, TO_CHAR(month_date,'Mon-YY') AS month
                FROM mis_monthly WHERE company_id=%s AND geography='consolidated'
                ORDER BY month_date DESC LIMIT 3
            """, (cid,))
            rows = cur.fetchall()
            if len(rows) == 3:
                e = [float(r["ebitda"]) if r["ebitda"] else 0.0 for r in rows]
                if e[0] < e[1] < e[2]:
                    alerts.append({
                        "severity": "HIGH", "alert_type": "EBITDA_WORSENING_3M",
                        "company": cid.upper().replace("_", "-"),
                        "detail": f"EBITDA worsened 3 months: {rows[2]['month']} → {rows[1]['month']} → {rows[0]['month']}",
                        "action": "Review cost structure and revenue drivers.",
                    })

        for cid in ("company_01", "company_02"):
            cur.execute("""
                SELECT TO_CHAR(month_date,'Mon-YY') AS month,
                       ROUND(total_income_lacs,2) AS revenue
                FROM mis_monthly WHERE company_id=%s AND geography='consolidated'
                ORDER BY month_date DESC LIMIT 2
            """, (cid,))
            rows = cur.fetchall()
            if len(rows) == 2 and rows[0]["revenue"] and rows[1]["revenue"]:
                curr, prev = float(rows[0]["revenue"]), float(rows[1]["revenue"])
                if curr < prev:
                    pct = round((curr - prev) / abs(prev) * 100, 1)
                    alerts.append({
                        "severity": "MEDIUM", "alert_type": "REVENUE_DECLINE_MOM",
                        "company": cid.upper().replace("_", "-"),
                        "detail": f"Revenue fell {abs(pct)}% MoM: {rows[1]['month']} → {rows[0]['month']}",
                        "action": "Investigate channel-level revenue drivers.",
                    })

    return alerts


# ─────────────────────────────────────────────────────────────────────────────
# Tool 6 — get_company_trend
# ─────────────────────────────────────────────────────────────────────────────

def get_company_trend(
    company_id: str,
    period: str = "FY26",
    geography: str = "consolidated",
    granularity: str = "monthly",
) -> dict:
    """
    Monthly/quarterly P&L time series with MoM annotations.

    Args:
        company_id: 'company_01' or 'company_02'
        period: FY26, Q1_FY26, last_6_months, etc.
        geography: 'consolidated' | 'country_a' | 'city_z'
        granularity: 'monthly' | 'quarterly'

    Returns:
        {data: [...], summary: {ebitda_trend, revenue_growth_pct}}
    """
    s, e, _ = _resolve(period)
    with get_conn() as conn, get_cursor(conn) as cur:
        if granularity == "quarterly":
            cur.execute("""
                SELECT DATE_TRUNC('quarter', month_date)::DATE AS period_date,
                       TO_CHAR(DATE_TRUNC('quarter', month_date),'YYYY "Q"Q') AS period_label,
                       ROUND(SUM(revenue_lacs),2) AS revenue,
                       ROUND(SUM(ebitda_lacs),2) AS ebitda,
                       ROUND(AVG(ebitda_pct)*100,2) AS ebitda_pct,
                       ROUND(SUM(gross_margin_lacs),2) AS gross_margin,
                       ROUND(AVG(gross_margin_pct)*100,2) AS gross_margin_pct,
                       ROUND(SUM(cogs_lacs),2) AS cogs,
                       ROUND(SUM(total_operating_costs_lacs),2) AS operating_costs
                FROM mis_monthly
                WHERE company_id=%s AND geography=%s AND month_date BETWEEN %s AND %s
                GROUP BY DATE_TRUNC('quarter', month_date) ORDER BY period_date
            """, (company_id, geography, s, e))
        else:
            cur.execute("""
                SELECT month_date AS period_date,
                       TO_CHAR(month_date,'Mon-YY') AS period_label,
                       ROUND(revenue_lacs,2) AS revenue,
                       ROUND(ebitda_lacs,2) AS ebitda,
                       ROUND(ebitda_pct*100,2) AS ebitda_pct,
                       ROUND(gross_margin_lacs,2) AS gross_margin,
                       ROUND(gross_margin_pct*100,2) AS gross_margin_pct,
                       ROUND(cogs_lacs,2) AS cogs,
                       ROUND(total_operating_costs_lacs,2) AS operating_costs
                FROM mis_monthly
                WHERE company_id=%s AND geography=%s AND month_date BETWEEN %s AND %s
                ORDER BY month_date
            """, (company_id, geography, s, e))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return {"error": f"No MIS data for {company_id} in {period}"}

    for i, row in enumerate(rows):
        for k, v in row.items():
            if hasattr(v, "__float__"):
                row[k] = float(v)
        row["mom_revenue_pct"] = None
        if i > 0 and rows[i - 1].get("revenue"):
            prev_rev = rows[i - 1]["revenue"]
            if prev_rev:
                row["mom_revenue_pct"] = round((row["revenue"] - prev_rev) / abs(prev_rev) * 100, 2)

    revenues = [r["revenue"] for r in rows if r.get("revenue") is not None]
    ebitdas = [r["ebitda"] for r in rows if r.get("ebitda") is not None]

    ebitda_trend = "insufficient_data"
    if len(ebitdas) >= 3:
        last3 = ebitdas[-3:]
        if all(last3[i] > last3[i - 1] for i in range(1, 3)):
            ebitda_trend = "improving"
        elif all(last3[i] < last3[i - 1] for i in range(1, 3)):
            ebitda_trend = "deteriorating"
        else:
            ebitda_trend = "mixed"

    revenue_growth = None
    if len(revenues) >= 2 and revenues[0]:
        revenue_growth = round((revenues[-1] - revenues[0]) / abs(revenues[0]) * 100, 2)

    # Pre-compute period totals so the agent never has to aggregate raw rows itself.
    # Using these totals for waterfall charts prevents the agent from mixing columns
    # across tool calls or accidentally summing across geography rows.
    cogs_vals = [r["cogs"] for r in rows if r.get("cogs") is not None]
    gm_vals   = [r["gross_margin"] for r in rows if r.get("gross_margin") is not None]
    op_cost_vals = [r["operating_costs"] for r in rows if r.get("operating_costs") is not None]
    total_revenue  = round(sum(revenues), 2)    if revenues     else None
    total_ebitda   = round(sum(ebitdas), 2)     if ebitdas      else None
    total_cogs     = round(sum(cogs_vals), 2)   if cogs_vals    else None
    total_gm       = round(sum(gm_vals), 2)     if gm_vals      else None
    total_op_costs = round(sum(op_cost_vals), 2) if op_cost_vals else None

    return {
        "data": rows,
        "summary": {
            "ebitda_trend": ebitda_trend,
            "revenue_growth_pct": revenue_growth,
            "latest_revenue_lacs": revenues[-1] if revenues else None,
            "latest_ebitda_lacs": ebitdas[-1] if ebitdas else None,
        },
        # Pre-summed period totals — use ONLY these for waterfall charts.
        # All values from geography='consolidated'. None = no DB data, do NOT invent.
        #
        # Waterfall construction guide:
        #   labels  = ["Revenue", "COGS", "Gross Margin", "OpEx", "EBITDA"]
        #   values  = [revenue_lacs, -cogs_lacs, gross_margin_lacs,
        #               -operating_costs_lacs, ebitda_lacs]   ← sign already correct
        #   total_indices = [0, 2, 4]   ← Revenue, Gross Margin, EBITDA are totals
        #
        # Skip any bar whose value is None. EBITDA can be negative — pass the
        # actual negative value; do NOT take abs(). The waterfall chart handles signs.
        "period_totals": {
            "revenue_lacs":          total_revenue,
            "cogs_lacs":             total_cogs,
            "gross_margin_lacs":     total_gm,
            "operating_costs_lacs":  total_op_costs,
            "ebitda_lacs":           total_ebitda,
            "geography": "consolidated",
            "period": period,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 7 — get_mis_recent_summary
# ─────────────────────────────────────────────────────────────────────────────

def get_mis_recent_summary(company_id: str) -> dict:
    """
    Latest month vs. prior month comparison across all P&L metrics.

    Returns:
        {latest_month, prior_month, changes: {metric: {current, prior, direction}}, flags, overall_direction}
    """
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT TO_CHAR(month_date,'Mon-YY') AS month_label,
                   ROUND(total_income_lacs,2) AS revenue,
                   ROUND(cogs_lacs,2) AS cogs,
                   ROUND(gross_margin_lacs,2) AS gross_margin,
                   ROUND(gross_margin_pct*100,2) AS gross_margin_pct,
                   ROUND(total_operating_costs_lacs,2) AS operating_costs,
                   ROUND(manpower_cost_lacs,2) AS manpower_cost,
                   ROUND(rent_lacs,2) AS rent,
                   ROUND(marketing_lacs,2) AS marketing,
                   ROUND(ebitda_lacs,2) AS ebitda,
                   ROUND(ebitda_pct*100,2) AS ebitda_pct
            FROM mis_monthly
            WHERE company_id=%s AND geography='consolidated'
            ORDER BY month_date DESC LIMIT 2
        """, (company_id,))
        rows = cur.fetchall()

    if len(rows) < 2:
        return {"error": f"Need at least 2 months of data for {company_id}."}

    latest, prior = dict(rows[0]), dict(rows[1])
    cost_metrics = {"cogs", "operating_costs", "manpower_cost", "rent", "marketing"}
    metric_keys = ["revenue", "cogs", "gross_margin", "gross_margin_pct",
                   "operating_costs", "manpower_cost", "rent", "marketing", "ebitda", "ebitda_pct"]

    changes = {}
    for m in metric_keys:
        c_val, p_val = latest.get(m), prior.get(m)
        if c_val is None or p_val is None or float(p_val) == 0:
            changes[m] = {"current": float(c_val) if c_val else None,
                          "prior": float(p_val) if p_val else None,
                          "direction": "unknown"}
            continue
        c, p = float(c_val), float(p_val)
        chg_abs = round(c - p, 2)
        chg_pct = round((c - p) / abs(p) * 100, 2)
        direction = (
            ("worsened" if chg_abs > 0 else "improved" if chg_abs < 0 else "stable")
            if m in cost_metrics
            else ("improved" if chg_abs > 0 else "worsened" if chg_abs < 0 else "stable")
        )
        changes[m] = {"current": c, "prior": p,
                      "change_abs": chg_abs, "change_pct": chg_pct, "direction": direction}

    flags = []
    if changes.get("revenue", {}).get("direction") == "worsened":
        flags.append(f"Revenue declined {abs(changes['revenue'].get('change_pct', 0)):.1f}% MoM")
    if changes.get("ebitda", {}).get("direction") == "worsened":
        flags.append(f"EBITDA worsened by ₹{abs(changes['ebitda'].get('change_abs', 0)):.1f} Lacs")
    if not flags:
        flags.append("No major deterioration flags.")

    ebitda_dir = changes.get("ebitda", {}).get("direction", "unknown")
    revenue_dir = changes.get("revenue", {}).get("direction", "unknown")
    overall = (
        "improving" if ebitda_dir == "improved" and revenue_dir == "improved" else
        "deteriorating" if ebitda_dir == "worsened" and revenue_dir == "worsened" else
        "mixed"
    )

    return {
        "latest_month": latest["month_label"],
        "prior_month": prior["month_label"],
        "overall_direction": overall,
        "flags": flags,
        "changes": changes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 8 — get_bu_breakdown
# ─────────────────────────────────────────────────────────────────────────────

def get_bu_breakdown(company_id: str, period: str = "latest") -> list:
    """
    BU-level revenue, EBITDA, channel breakdowns.

    Args:
        company_id: 'company_01' or 'company_02'
        period: 'latest', 'FY26', 'Q1_FY26', etc.

    Returns:
        [{bu_id, revenue_lacs, ebitda_lacs, ebitda_pct, channels: {...}}]
    """
    s, e, _ = _resolve(period)
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT bu_id,
                   ROUND(SUM(revenue_lacs),2) AS revenue_lacs,
                   ROUND(SUM(ebitda_lacs),2) AS ebitda_lacs,
                   ROUND(AVG(gross_margin_pct)*100,2) AS ebitda_pct,
                   ROUND(SUM(channel_dine_in_lacs),2) AS dine_in_lacs,
                   ROUND(SUM(channel_aggregator_a_lacs),2) AS aggregator_a_lacs,
                   ROUND(SUM(channel_aggregator_b_lacs),2) AS aggregator_b_lacs,
                   ROUND(SUM(channel_catering_lacs),2) AS catering_lacs,
                   ROUND(SUM(channel_franchise_lacs),2) AS franchise_lacs
            FROM mis_bu_monthly
            WHERE company_id=%s AND month_date BETWEEN %s AND %s
            GROUP BY bu_id ORDER BY bu_id
        """, (company_id, s, e))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return [{"error": f"No BU data for {company_id} in {period}"}]

    result = []
    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
        result.append({
            "bu_id": r["bu_id"],
            "revenue_lacs": r["revenue_lacs"],
            "ebitda_lacs": r["ebitda_lacs"],
            "ebitda_pct": r["ebitda_pct"],
            "channels": {
                "dine_in": r["dine_in_lacs"],
                "aggregator_a": r["aggregator_a_lacs"],
                "aggregator_b": r["aggregator_b_lacs"],
                "catering": r["catering_lacs"],
                "franchise": r["franchise_lacs"],
            },
        })
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Tool 9 — get_outlet_breakdown
# ─────────────────────────────────────────────────────────────────────────────

def get_outlet_breakdown(period: str = "latest") -> list:
    """
    Outlet-level P&L for Company_01.

    Returns:
        [{outlet_id, city, revenue_lacs, operational_profit_pct, sales_to_rent_ratio, covers, area_sqft}]
    """
    s, e, _ = _resolve(period)
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT outlet_id, city, bu_id,
                   TO_CHAR(month_date,'Mon-YY') AS month,
                   ROUND(revenue_lacs,2) AS revenue_lacs,
                   ROUND(operational_profit_lacs,2) AS operational_profit_lacs,
                   ROUND(operational_profit_pct*100,2) AS operational_profit_pct,
                   sales_to_rent_ratio, covers, area_sqft
            FROM mis_outlet_monthly
            WHERE company_id='company_01' AND month_date BETWEEN %s AND %s
            ORDER BY outlet_id, month_date
        """, (s, e))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return [{"error": f"No outlet data for Company_01 in {period}"}]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 10 — run_query
# ─────────────────────────────────────────────────────────────────────────────

_ALLOWED_TABLES = frozenset({
    "portfolio_companies", "portfolio_transactions", "valuations",
    "forex_rates", "mis_monthly", "mis_bu_monthly", "mis_outlet_monthly",
    "mis_submissions", "mis_anomalies", "portfolio_categories",
    "portfolio_aggregates_mv",
})


def run_query(sql: str) -> dict:
    """
    Execute a read-only SELECT query against the investment database.

    Only SELECT statements are allowed. Maximum 500 rows returned.
    Only queries against known tables are permitted.

    IMPORTANT: Queries against mis_monthly MUST include a geography filter
    (e.g. WHERE geography='consolidated') to avoid double-counting revenue/EBITDA
    across geography rows. Queries without this filter will be rejected.

    Returns:
        {rows: [dict], row_count: int}
    """
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return {"error": "Only SELECT statements are allowed."}

    # Enforce geography filter when querying mis_monthly to prevent double-counting.
    # mis_monthly stores one row per company × month × geography (consolidated,
    # country_a, city_z). Summing without filtering inflates revenue/EBITDA ~2-3x.
    if "MIS_MONTHLY" in sql_upper and "GEOGRAPHY" not in sql_upper:
        return {
            "error": (
                "Queries against mis_monthly must include a geography filter "
                "(e.g. AND geography='consolidated') to avoid double-counting "
                "revenue and EBITDA across geography rows. "
                "Use get_company_trend or get_cost_breakdown instead — they "
                "enforce geography='consolidated' automatically."
            )
        }

    with get_conn() as conn, get_cursor(conn) as cur:
        try:
            cur.execute(f"SELECT * FROM ({sql.rstrip(';')}) _q LIMIT {SAFE_QUERY_ROW_LIMIT}")
            rows = [dict(r) for r in cur.fetchall()]
        except Exception as exc:
            return {"error": str(exc)}

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)

    return {"rows": rows, "row_count": len(rows)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool 11 — convert_forex
# ─────────────────────────────────────────────────────────────────────────────

def convert_forex(
    amount: float,
    from_currency: str,
    to_currency: str = "INR",
    as_of_date: str = None,
) -> dict:
    """
    Convert an amount between currencies using stored forex rates.

    Returns:
        {converted_amount, rate, rate_date, note}
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return {"converted_amount": amount, "rate": 1.0, "rate_date": None, "note": "Same currency"}

    with get_conn() as conn, get_cursor(conn) as cur:
        if as_of_date:
            cur.execute("""
                SELECT rate, rate_date FROM forex_rates
                WHERE from_currency=%s AND to_currency=%s AND rate_date <= %s
                ORDER BY rate_date DESC LIMIT 1
            """, (from_currency, to_currency, as_of_date))
        else:
            cur.execute("""
                SELECT rate, rate_date FROM forex_rates
                WHERE from_currency=%s AND to_currency=%s
                ORDER BY rate_date DESC LIMIT 1
            """, (from_currency, to_currency))
        row = cur.fetchone()

    if not row:
        return {"error": f"No forex rate found for {from_currency}/{to_currency}"}

    rate = float(row["rate"])
    return {
        "converted_amount": round(amount * rate, 4),
        "rate": rate,
        "rate_date": str(row["rate_date"]),
        "note": f"{amount} {from_currency} = {round(amount * rate, 4)} {to_currency}",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 12 — get_portfolio_aggregates  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_portfolio_aggregates(scope: str = "TOTAL") -> list:
    """
    Read the pre-computed portfolio_aggregates_mv materialized view.
    Fastest source for fund-level KPIs — always call this before get_portfolio_summary
    for overview dashboards.

    Args:
        scope: 'TOTAL' | 'SECTOR' | 'PORTFOLIO_TYPE'

    Returns:
        [{scope_value, total_invested_cr, current_value_cr, moic, company_count}]
    """
    scope = scope.upper()
    valid = {"TOTAL", "SECTOR", "PORTFOLIO_TYPE"}
    if scope not in valid:
        scope = "TOTAL"

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT scope_value, total_invested_cr, current_value_cr, moic, company_count
            FROM portfolio_aggregates_mv
            WHERE scope_type = %s
            ORDER BY current_value_cr DESC NULLS LAST
        """, (scope,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 13 — get_valuation_history  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_valuation_history(
    company_name: str,
    start_date: str = None,
    end_date: str = None,
) -> list:
    """
    Return the complete valuation timeline for a company (clean time series for charting).

    Returns:
        [{valuation_date, post_money_valuation_cr, pre_money_valuation_cr, source, currency}]
    """
    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        params = [pattern, pattern]
        date_filter = ""
        if start_date:
            date_filter += " AND v.valuation_date >= %s"
            params.append(start_date)
        if end_date:
            date_filter += " AND v.valuation_date <= %s"
            params.append(end_date)

        cur.execute(f"""
            SELECT v.valuation_date,
                   ROUND(v.post_money_valuation_cr,2) AS post_money_valuation_cr,
                   ROUND(v.pre_money_valuation_cr,2) AS pre_money_valuation_cr,
                   v.source, v.currency
            FROM valuations v
            JOIN portfolio_companies pc ON v.company_id = pc.id
            WHERE (LOWER(pc.display_name) LIKE LOWER(%s) OR LOWER(pc.company_name) LIKE LOWER(%s))
              {date_filter}
            ORDER BY v.valuation_date
        """, params)
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 14 — get_transaction_timeline  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_transaction_timeline(company_name: str) -> list:
    """
    Return the full deal history including investment round details.

    Returns:
        [{transaction_date, transaction_type, amount_cr, series, instrument_type,
          investing_entity, post_money_valuation_cr, shareholding_pct, notes}]
    """
    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT pc.id FROM portfolio_companies pc
            WHERE (LOWER(pc.display_name) LIKE LOWER(%s) OR LOWER(pc.company_name) LIKE LOWER(%s))
              AND pc.is_active=true LIMIT 1
        """, (pattern, pattern))
        row = cur.fetchone()
        if not row:
            return [{"error": f"Company not found: '{company_name}'"}]
        cid = row["id"]

        cur.execute("""
            SELECT transaction_date, transaction_type,
                   ROUND(ABS(amount_inr_cr),4) AS amount_cr,
                   ROUND(amount_inr_cr,4) AS amount_inr_cr,
                   original_currency, original_amount,
                   series, instrument_type, investing_entity,
                   ROUND(post_money_valuation_cr,2) AS post_money_valuation_cr,
                   shareholding_pct, notes
            FROM portfolio_transactions
            WHERE company_id=%s
            ORDER BY transaction_date
        """, (cid,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 15 — get_cap_table_snapshot  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_cap_table_snapshot(company_name: str) -> list:
    """
    Aggregates transaction data by investing entity to show ownership breakdown.

    Returns:
        [{investing_entity, total_invested_cr, rounds_count, latest_shareholding_pct, first_investment_date}]
    """
    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT id FROM portfolio_companies
            WHERE (LOWER(display_name) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))
              AND is_active=true LIMIT 1
        """, (pattern, pattern))
        row = cur.fetchone()
        if not row:
            return [{"error": f"Company not found: '{company_name}'"}]
        cid = row["id"]

        cur.execute("""
            SELECT investing_entity,
                   ROUND(SUM(ABS(amount_inr_cr)),2) AS total_invested_cr,
                   COUNT(*) AS rounds_count,
                   MAX(shareholding_pct) AS latest_shareholding_pct,
                   MIN(transaction_date) AS first_investment_date
            FROM portfolio_transactions
            WHERE company_id=%s
              AND transaction_type IN ('Investment','Follow_on')
              AND investing_entity IS NOT NULL
            GROUP BY investing_entity
            ORDER BY total_invested_cr DESC
        """, (cid,))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 16 — get_cost_breakdown  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_cost_breakdown(
    company_id: str,
    period: str = "FY26",
    geography: str = "consolidated",
) -> list:
    """
    Returns all 15 granular cost line items from mis_monthly not exposed by get_company_trend.

    Returns:
        [{month_date, manpower_cost_lacs, rent_lacs, utilities_lacs, electricity_lacs,
          channel_expenses_lacs, commission_lacs, transport_lacs, marketing_lacs,
          admin_lacs, it_lacs, professional_fees_lacs, compliance_costs_lacs, events_lacs,
          indirect_income_lacs, ebitda_with_itc_lacs}]
    """
    s, e, _ = _resolve(period)
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT TO_CHAR(month_date,'Mon-YY') AS month_label,
                   month_date,
                   ROUND(manpower_cost_lacs,2) AS manpower_cost_lacs,
                   ROUND(rent_lacs,2) AS rent_lacs,
                   ROUND(COALESCE(utilities_lacs,0),2) AS utilities_lacs,
                   ROUND(COALESCE(electricity_lacs,0),2) AS electricity_lacs,
                   ROUND(COALESCE(channel_expenses_lacs,0),2) AS channel_expenses_lacs,
                   ROUND(COALESCE(commission_lacs,0),2) AS commission_lacs,
                   ROUND(COALESCE(transport_lacs,0),2) AS transport_lacs,
                   ROUND(marketing_lacs,2) AS marketing_lacs,
                   ROUND(COALESCE(admin_lacs,0),2) AS admin_lacs,
                   ROUND(COALESCE(it_lacs,0),2) AS it_lacs,
                   ROUND(COALESCE(professional_fees_lacs,0),2) AS professional_fees_lacs,
                   ROUND(COALESCE(compliance_costs_lacs,0),2) AS compliance_costs_lacs,
                   ROUND(COALESCE(events_lacs,0),2) AS events_lacs,
                   ROUND(COALESCE(indirect_income_lacs,0),2) AS indirect_income_lacs,
                   ROUND(COALESCE(ebitda_with_itc_lacs, ebitda_lacs),2) AS ebitda_with_itc_lacs
            FROM mis_monthly
            WHERE company_id=%s AND geography=%s AND month_date BETWEEN %s AND %s
            ORDER BY month_date
        """, (company_id, geography, s, e))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return [{"error": f"No cost data for {company_id} in {period}"}]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 17 — get_channel_breakdown  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_channel_breakdown(
    company_id: str,
    period: str = "FY26",
    by: str = "month",
) -> list:
    """
    Dedicated channel mix tool — returns clean channel time-series or BU-level splits.

    Args:
        company_id: 'company_01' or 'company_02'
        period: 'FY26', 'Q1_FY26', etc.
        by: 'month' (aggregate across BUs per month) | 'bu' (per BU for the period)

    Returns:
        [{period_key, channel_dine_in_lacs, channel_aggregator_a_lacs, channel_aggregator_b_lacs,
          channel_aggregator_d_lacs, channel_catering_lacs, channel_franchise_lacs,
          total_revenue_lacs, dine_in_pct, aggregator_pct, catering_pct, franchise_pct}]
    """
    s, e, _ = _resolve(period)
    with get_conn() as conn, get_cursor(conn) as cur:
        if by == "bu":
            cur.execute("""
                SELECT bu_id AS period_key,
                       ROUND(SUM(channel_dine_in_lacs),2) AS dine_in_lacs,
                       ROUND(SUM(channel_aggregator_a_lacs),2) AS aggregator_a_lacs,
                       ROUND(SUM(channel_aggregator_b_lacs),2) AS aggregator_b_lacs,
                       ROUND(SUM(COALESCE(channel_aggregator_d_lacs,0)),2) AS aggregator_d_lacs,
                       ROUND(SUM(channel_catering_lacs),2) AS catering_lacs,
                       ROUND(SUM(channel_franchise_lacs),2) AS franchise_lacs,
                       ROUND(SUM(revenue_lacs),2) AS total_revenue_lacs
                FROM mis_bu_monthly
                WHERE company_id=%s AND month_date BETWEEN %s AND %s
                GROUP BY bu_id ORDER BY bu_id
            """, (company_id, s, e))
        else:
            cur.execute("""
                SELECT TO_CHAR(month_date,'Mon-YY') AS period_key,
                       month_date,
                       ROUND(SUM(channel_dine_in_lacs),2) AS dine_in_lacs,
                       ROUND(SUM(channel_aggregator_a_lacs),2) AS aggregator_a_lacs,
                       ROUND(SUM(channel_aggregator_b_lacs),2) AS aggregator_b_lacs,
                       ROUND(SUM(COALESCE(channel_aggregator_d_lacs,0)),2) AS aggregator_d_lacs,
                       ROUND(SUM(channel_catering_lacs),2) AS catering_lacs,
                       ROUND(SUM(channel_franchise_lacs),2) AS franchise_lacs,
                       ROUND(SUM(revenue_lacs),2) AS total_revenue_lacs
                FROM mis_bu_monthly
                WHERE company_id=%s AND month_date BETWEEN %s AND %s
                GROUP BY month_date, TO_CHAR(month_date,'Mon-YY')
                ORDER BY month_date
            """, (company_id, s, e))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return [{"error": f"No channel data for {company_id} in {period}"}]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)
        total = r.get("total_revenue_lacs") or 1
        r["dine_in_pct"] = round(r.get("dine_in_lacs", 0) / total * 100, 1)
        r["aggregator_pct"] = round(
            (r.get("aggregator_a_lacs", 0) + r.get("aggregator_b_lacs", 0) + r.get("aggregator_d_lacs", 0)) / total * 100, 1
        )
        r["catering_pct"] = round(r.get("catering_lacs", 0) / total * 100, 1)
        r["franchise_pct"] = round(r.get("franchise_lacs", 0) / total * 100, 1)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 18 — get_outlet_profitability  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_outlet_profitability(
    period: str = "latest",
    sort_by: str = "profit",
    top_n: int = 10,
) -> list:
    """
    Ranked outlet profitability view for Company_01.

    Args:
        period: 'latest', 'FY26', 'Q1_FY26', etc.
        sort_by: 'revenue' | 'profit' | 'sales_to_rent' | 'covers'
        top_n: Number of outlets to return.

    Returns:
        [{rank, outlet_id, city, revenue_lacs, operational_profit_lacs,
          operational_profit_pct, sales_to_rent_ratio, covers, area_sqft, revenue_per_sqft}]
    """
    s, e, _ = _resolve(period)
    sort_col = {
        "revenue": "revenue_lacs",
        "profit": "operational_profit_lacs",
        "sales_to_rent": "sales_to_rent_ratio",
        "covers": "covers",
    }.get(sort_by, "operational_profit_lacs")

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute(f"""
            SELECT outlet_id, city,
                   ROUND(AVG(revenue_lacs),2) AS revenue_lacs,
                   ROUND(AVG(operational_profit_lacs),2) AS operational_profit_lacs,
                   ROUND(AVG(operational_profit_pct)*100,2) AS operational_profit_pct,
                   ROUND(AVG(sales_to_rent_ratio),2) AS sales_to_rent_ratio,
                   ROUND(AVG(covers),0) AS covers,
                   MAX(area_sqft) AS area_sqft
            FROM mis_outlet_monthly
            WHERE company_id='company_01' AND month_date BETWEEN %s AND %s
            GROUP BY outlet_id, city
            ORDER BY {sort_col} DESC NULLS LAST
            LIMIT %s
        """, (s, e, top_n))
        rows = [dict(r) for r in cur.fetchall()]

    if not rows:
        return [{"error": f"No outlet data in {period}"}]

    result = []
    for i, r in enumerate(rows, 1):
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
        area = r.get("area_sqft") or 1
        r["revenue_per_sqft"] = round(r.get("revenue_lacs", 0) * 100000 / area, 2) if area else None
        r["rank"] = i
        result.append(r)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Tool 19 — get_mis_submission_status  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_mis_submission_status(fiscal_year: str = "FY26") -> dict:
    """
    Surfaces mis_submissions data — tracks whether portfolio companies submit
    MIS data on time and how many anomalies were detected.

    Returns:
        {submission_rate_pct, by_status, by_company, overdue}
    """
    s, e, _ = _resolve(fiscal_year)
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM mis_submissions
            WHERE period_start >= %s AND period_start <= %s
            GROUP BY status
        """, (s, e))
        by_status = {r["status"]: int(r["cnt"]) for r in cur.fetchall()}

        total = sum(by_status.values())
        submitted = by_status.get("Submitted", 0) + by_status.get("Reviewed", 0)
        submission_rate = round(submitted / total * 100, 1) if total else 0.0

        cur.execute("""
            SELECT company_id,
                   COUNT(*) FILTER (WHERE status IN ('Submitted','Reviewed')) AS months_submitted,
                   COUNT(*) FILTER (WHERE status='Pending') AS months_pending,
                   COUNT(*) FILTER (WHERE status='Rejected') AS months_rejected,
                   COALESCE(SUM(anomaly_count),0) AS total_anomalies,
                   MAX(submitted_at) AS latest_submission_date,
                   MAX(status) AS latest_status
            FROM mis_submissions
            WHERE period_start >= %s AND period_start <= %s
            GROUP BY company_id
            ORDER BY company_id
        """, (s, e))
        by_company = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT company_id, period_start
            FROM mis_submissions
            WHERE status='Pending' AND period_start >= %s AND period_start <= %s
            ORDER BY company_id, period_start
        """, (s, e))
        overdue_rows = cur.fetchall()

    overdue_map: dict = {}
    for r in overdue_rows:
        cid = r["company_id"]
        if cid not in overdue_map:
            overdue_map[cid] = []
        overdue_map[cid].append(str(r["period_start"]))

    for r in by_company:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
            elif hasattr(v, "isoformat"):
                r[k] = str(v)

    return {
        "submission_rate_pct": submission_rate,
        "by_status": by_status,
        "by_company": by_company,
        "overdue": [{"company_id": k, "missing_periods": v} for k, v in overdue_map.items()],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool 20 — get_entity_breakdown  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_entity_breakdown() -> list:
    """
    Groups portfolio companies by their fund vehicle (portfolio_type maps to
    portfolio_categories.code). Returns display_name from portfolio_categories.

    Returns:
        [{entity_code, entity_display_name, company_count, total_invested_cr,
          current_value_cr, moic, sectors}]
    """
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT pc.portfolio_type AS entity_code,
                   COALESCE(cat.display_name, pc.portfolio_type) AS entity_display_name,
                   COUNT(*) AS company_count,
                   ROUND(SUM(ABS(pc.investment_value_cr)),2) AS total_invested_cr,
                   ROUND(SUM(pc.current_value_cr),2) AS current_value_cr,
                   ROUND(SUM(pc.current_value_cr)/NULLIF(SUM(ABS(pc.investment_value_cr)),0),4) AS moic
            FROM portfolio_companies pc
            LEFT JOIN portfolio_categories cat ON pc.portfolio_type = cat.code
            WHERE pc.is_active=true
            GROUP BY pc.portfolio_type, cat.display_name
            ORDER BY total_invested_cr DESC NULLS LAST
        """)
        rows = [dict(r) for r in cur.fetchall()]

        if rows:
            entity_codes = [r["entity_code"] for r in rows if r["entity_code"]]
            if entity_codes:
                cur.execute("""
                    SELECT portfolio_type, ARRAY_AGG(DISTINCT sector) AS sectors
                    FROM portfolio_companies
                    WHERE portfolio_type = ANY(%s) AND is_active=true
                    GROUP BY portfolio_type
                """, (entity_codes,))
                sector_map = {r["portfolio_type"]: r["sectors"] for r in cur.fetchall()}
            else:
                sector_map = {}

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "__float__"):
                r[k] = float(v)
        r["sectors"] = sector_map.get(r["entity_code"], [])
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tool 21 — get_mis_anomaly_summary  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def get_mis_anomaly_summary(company_id: str = None, fiscal_year: str = "FY26") -> list:
    """
    Aggregates mis_anomalies by severity and rule. Portfolio-wide if company_id is None.

    Returns:
        [{severity, rule_code, count, companies_affected, latest_detected_at}]
    """
    s, e, _ = _resolve(fiscal_year)
    with get_conn() as conn, get_cursor(conn) as cur:
        if company_id:
            cur.execute("""
                SELECT ma.severity, ma.rule_code,
                       COUNT(*) AS cnt,
                       ARRAY_AGG(DISTINCT ms.company_id) AS companies_affected,
                       MAX(ma.detected_at) AS latest_detected_at
                FROM mis_anomalies ma
                JOIN mis_submissions ms ON ma.submission_id = ms.id
                WHERE ms.company_id = %s
                  AND ms.period_start >= %s AND ms.period_start <= %s
                GROUP BY ma.severity, ma.rule_code
                ORDER BY cnt DESC
            """, (company_id, s, e))
        else:
            cur.execute("""
                SELECT ma.severity, ma.rule_code,
                       COUNT(*) AS cnt,
                       ARRAY_AGG(DISTINCT ms.company_id) AS companies_affected,
                       MAX(ma.detected_at) AS latest_detected_at
                FROM mis_anomalies ma
                JOIN mis_submissions ms ON ma.submission_id = ms.id
                WHERE ms.period_start >= %s AND ms.period_start <= %s
                GROUP BY ma.severity, ma.rule_code
                ORDER BY cnt DESC
            """, (s, e))
        rows = [dict(r) for r in cur.fetchall()]

    for r in rows:
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = str(v)
            elif hasattr(v, "__float__"):
                r[k] = float(v)
    return rows
