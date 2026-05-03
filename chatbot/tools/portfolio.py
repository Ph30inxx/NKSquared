"""
Portfolio tools: get_portfolio_summary, get_company_portfolio_detail,
calculate_irr, check_portfolio_alerts.

Queries: portfolio_companies, portfolio_transactions, valuations.
"""
import json
from datetime import date
from chatbot.db import get_conn, get_cursor


def get_portfolio_summary(
    group_by: str = "sector",
    include_written_off: bool = True,
) -> str:
    """
    Return a structured JSON portfolio summary with totals, dimension breakdowns,
    top performers, flagged companies, and realized exits.

    Args:
        group_by: Breakdown dimension — 'sector' | 'portfolio_type' |
                  'asset_class' | 'investment_status'. Default: 'sector'.
        include_written_off: Include written-off companies in totals. Default: True.

    Returns:
        JSON with keys: totals, breakdown_by_<dim>, top_5_performers,
        flagged_companies, realized_exits.
    """
    valid_cols = {
        "sector": "sector",
        "portfolio_type": "portfolio_type",
        "asset_class": "asset_class",
        "investment_status": "investment_status",
    }
    group_col = valid_cols.get(group_by, "sector")

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE portfolio_status='Unrealized') AS unrealized_count,
                COUNT(*) FILTER (WHERE portfolio_status='Realized')   AS realized_count,
                COUNT(*) FILTER (WHERE investment_status='Written_off') AS written_off_count,
                COUNT(*) AS total_count,
                ROUND(SUM(ABS(investment_value_cr)),2) AS total_invested_cr,
                ROUND(SUM(current_value_cr),2)         AS total_current_cr,
                ROUND(SUM(current_value_cr)/NULLIF(SUM(ABS(investment_value_cr)),0),4) AS overall_moic
            FROM portfolio_companies
            WHERE is_active=true
              AND (investment_status!='Written_off' OR %s=true)
        """, (include_written_off,))
        totals = dict(cur.fetchone())

        cur.execute(f"""
            SELECT
                {group_col} AS group_name,
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
                   ROUND(moic,4) AS moic, investment_status, portfolio_status
            FROM portfolio_companies
            WHERE (moic<1.0 OR investment_status='Written_off') AND is_active=true
            ORDER BY moic ASC NULLS LAST LIMIT 15
        """)
        flagged = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT display_name AS company, investment_status,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr,
                   ROUND(current_value_cr,2) AS returned_cr,
                   ROUND(moic,4) AS moic
            FROM portfolio_companies
            WHERE portfolio_status='Realized' AND is_active=true
            ORDER BY moic DESC
        """)
        realized = [dict(r) for r in cur.fetchall()]

    return json.dumps({
        "totals": totals,
        f"breakdown_by_{group_by}": breakdown,
        "top_5_performers": top_performers,
        "flagged_companies": flagged,
        "realized_exits": realized,
    }, default=str)


def get_company_portfolio_detail(company_name: str) -> str:
    """
    Return full portfolio detail for a single company: position summary,
    full transaction history, and valuation history.

    Args:
        company_name: Company display_name or partial name (case-insensitive).

    Returns:
        JSON with keys: company (position row), transactions (list), valuations (list).
    """
    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT id, display_name, company_name, sector, sub_sector,
                   portfolio_type, investment_status, portfolio_status, asset_class,
                   date_of_first_investment,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic,
                   ROUND(irr*100,2) AS irr_pct,
                   country, currency, notes
            FROM portfolio_companies
            WHERE (LOWER(display_name) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))
              AND is_active=true
            LIMIT 1
        """, (pattern, pattern))
        company = cur.fetchone()
        if not company:
            return json.dumps({"error": f"Company not found: '{company_name}'"})
        company = dict(company)
        cid = company["id"]

        cur.execute("""
            SELECT transaction_date, transaction_type,
                   ROUND(amount_inr_cr,4) AS amount_inr_cr,
                   original_currency, original_amount, series,
                   instrument_type, investing_entity, shareholding_pct, ssa_reference
            FROM portfolio_transactions
            WHERE company_id=%s
            ORDER BY transaction_date
        """, (cid,))
        transactions = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT valuation_date,
                   ROUND(post_money_valuation_cr,2) AS post_money_cr,
                   ROUND(pre_money_valuation_cr,2)  AS pre_money_cr,
                   source, currency
            FROM valuations
            WHERE company_id=%s
            ORDER BY valuation_date DESC
        """, (cid,))
        valuations = [dict(r) for r in cur.fetchall()]

    return json.dumps(
        {"company": company, "transactions": transactions, "valuations": valuations},
        default=str,
    )


def calculate_irr(company_name: str) -> str:
    """
    Compute XIRR (annualised IRR) for a portfolio company using its dated
    cash-flow history from portfolio_transactions.

    The company's current_value_cr is appended as a synthetic positive inflow
    dated today to represent unrealised value.

    Args:
        company_name: Company display_name or partial name (case-insensitive).

    Returns:
        JSON with: company, irr_pct, moic, total_invested_cr, total_returned_cr,
        num_cash_flows, first_investment_date, holding_period_days.
    """
    try:
        from pyxirr import xirr as _xirr
    except ImportError:
        return json.dumps({"error": "pyxirr not installed in chatbot/requirements.txt."})

    pattern = f"%{company_name}%"
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT id, display_name,
                   ROUND(current_value_cr,2) AS current_value_cr,
                   ROUND(moic,4) AS moic
            FROM portfolio_companies
            WHERE (LOWER(display_name) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))
              AND is_active=true
            LIMIT 1
        """, (pattern, pattern))
        company = cur.fetchone()
        if not company:
            return json.dumps({"error": f"Company not found: '{company_name}'"})

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
        return json.dumps({"error": "No cash flow data found."})

    dates   = [r["transaction_date"] for r in rows]
    amounts = [float(r["amount_inr_cr"]) for r in rows]

    if company["current_value_cr"] and float(company["current_value_cr"]) > 0:
        dates.append(date.today())
        amounts.append(float(company["current_value_cr"]))

    if len(dates) < 2:
        return json.dumps({"error": "Need at least 2 cash flows to compute IRR."})

    try:
        irr = _xirr(dates, amounts)
    except Exception as exc:
        return json.dumps({"error": f"IRR computation failed: {exc}"})

    total_invested = sum(abs(a) for a in amounts if a < 0)
    total_returned = sum(a for a in amounts if a > 0)

    return json.dumps({
        "company": company["display_name"],
        "irr_pct": round(irr * 100, 2) if irr is not None else None,
        "moic": float(company["moic"]) if company["moic"] else None,
        "total_invested_cr": round(total_invested, 2),
        "total_returned_cr": round(total_returned, 2),
        "num_cash_flows": len(rows),
        "first_investment_date": str(dates[0]),
        "holding_period_days": (date.today() - dates[0]).days,
    }, default=str)


def check_portfolio_alerts() -> str:
    """
    Scan the portfolio and MIS data for conditions that need attention:
    1. Active companies with MOIC < 0.95
    2. Written-off companies
    3. Company_01 / Company_02 EBITDA worsening 3 consecutive months
    4. Company_01 / Company_02 revenue declining MoM

    Returns:
        JSON with total_alerts, severity counts (high/medium/info),
        and a categorised alerts list.
    """
    alerts = []

    with get_conn() as conn, get_cursor(conn) as cur:
        # MOIC < 0.95 active unrealised
        cur.execute("""
            SELECT display_name AS company, sector, portfolio_type,
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
                "severity": "HIGH",
                "category": "Portfolio — MOIC Below 0.95",
                "company": r["company"],
                "detail": f"MOIC {r['moic']}x on ₹{r['invested_cr']} Cr invested. "
                          f"Current mark: ₹{r['current_value_cr']} Cr.",
                "action": "Review company health; consider impairment assessment.",
            })

        # Written off
        cur.execute("""
            SELECT display_name AS company,
                   ROUND(ABS(investment_value_cr),2) AS invested_cr
            FROM portfolio_companies
            WHERE investment_status='Written_off' AND is_active=true
        """)
        for r in cur.fetchall():
            alerts.append({
                "severity": "INFO",
                "category": "Portfolio — Written Off",
                "company": r["company"],
                "detail": f"₹{r['invested_cr']} Cr written off.",
                "action": "No action unless reassessment requested.",
            })

        # EBITDA worsening 3 consecutive months
        for cid in ("company_01", "company_02"):
            cur.execute("""
                SELECT ROUND(ebitda_lacs,2) AS ebitda,
                       TO_CHAR(month_date,'Mon-YY') AS month
                FROM mis_monthly
                WHERE company_id=%s AND geography='consolidated'
                ORDER BY month_date DESC LIMIT 3
            """, (cid,))
            rows = cur.fetchall()
            if len(rows) == 3:
                # Handle None values for EBITDA (e.g. missing data) by treating them as 0.0
                e = [float(r["ebitda"]) if r["ebitda"] is not None else 0.0 for r in rows]
                if e[0] < e[1] < e[2]:
                    alerts.append({
                        "severity": "HIGH",
                        "category": "MIS — EBITDA Worsening",
                        "company": cid.upper().replace("_", "-"),
                        "detail": (
                            f"EBITDA deteriorated 3 consecutive months: "
                            f"{rows[2]['month']} ({e[2]:.1f}L) → "
                            f"{rows[1]['month']} ({e[1]:.1f}L) → "
                            f"{rows[0]['month']} ({e[0]:.1f}L)"
                        ),
                        "action": "Review cost structure and revenue drivers immediately.",
                    })

        # Revenue declining MoM
        for cid in ("company_01", "company_02"):
            cur.execute("""
                SELECT TO_CHAR(month_date,'Mon-YY') AS month,
                       ROUND(total_income_lacs,2) AS revenue
                FROM mis_monthly
                WHERE company_id=%s AND geography='consolidated'
                ORDER BY month_date DESC LIMIT 2
            """, (cid,))
            rows = cur.fetchall()
            if len(rows) == 2 and rows[0]["revenue"] and rows[1]["revenue"]:
                curr, prev = float(rows[0]["revenue"]), float(rows[1]["revenue"])
                if curr < prev:
                    pct = round((curr - prev) / abs(prev) * 100, 1)
                    alerts.append({
                        "severity": "MEDIUM",
                        "category": "MIS — Revenue Decline",
                        "company": cid.upper().replace("_", "-"),
                        "detail": (
                            f"Revenue fell {abs(pct)}% MoM: "
                            f"{rows[1]['month']} ₹{prev:.1f}L → "
                            f"{rows[0]['month']} ₹{curr:.1f}L"
                        ),
                        "action": "Investigate channel-level revenue drivers.",
                    })

    return json.dumps({
        "total_alerts": len(alerts),
        "high":   sum(1 for a in alerts if a["severity"] == "HIGH"),
        "medium": sum(1 for a in alerts if a["severity"] == "MEDIUM"),
        "info":   sum(1 for a in alerts if a["severity"] == "INFO"),
        "alerts": alerts,
    }, default=str)
