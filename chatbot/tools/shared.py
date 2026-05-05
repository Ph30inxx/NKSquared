"""
Shared tools: forex_converter, execute_safe_query,
find_similar_query, save_validated_query.
"""
import json
from chatbot.config import DB_URL_SYNC, SAFE_QUERY_ROW_LIMIT
from chatbot.db import get_conn, get_cursor

# Tables the execute_safe_query tool is permitted to touch
_ALLOWED_TABLES = {
    "portfolio_companies", "portfolio_transactions", "valuations",
    "forex_rates", "mis_monthly", "mis_bu_monthly", "mis_outlet_monthly",
    "mis_submissions", "nk_validated_queries",
}


def execute_safe_query(sql: str) -> str:
    """
    Execute a read-only SELECT query against the NKSquared database.
    Use this for ad-hoc questions not covered by the structured tools.

    Rules enforced automatically:
    - Only SELECT statements are accepted
    - Results are capped at 500 rows
    - Only NKSquared platform tables may be queried

    Args:
        sql: A SELECT SQL statement. Do not add a LIMIT clause — one is
             added automatically.

    Returns:
        JSON string with 'rows' (list of dicts) and 'row_count'.
        Returns an error JSON if validation fails.
    """
    stripped = sql.strip().rstrip(";")

    if not stripped.upper().startswith("SELECT"):
        return json.dumps({"error": "Only SELECT statements are permitted."})

    lower = stripped.lower()
    if not any(t in lower for t in _ALLOWED_TABLES):
        return json.dumps({
            "error": (
                "Query must reference at least one known table. "
                f"Allowed: {sorted(_ALLOWED_TABLES)}"
            )
        })

    capped = f"SELECT * FROM ({stripped}) _q LIMIT {SAFE_QUERY_ROW_LIMIT}"

    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            cur.execute(capped)
            rows = [dict(r) for r in cur.fetchall()]
        return json.dumps({"rows": rows, "row_count": len(rows)}, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def forex_converter(
    amount: float,
    from_currency: str,
    to_currency: str,
    as_of_date: str = None,
) -> str:
    """
    Convert an amount between currencies using rates stored in forex_rates.

    Args:
        amount: The amount to convert.
        from_currency: Source currency code ('INR', 'AED', 'USD', 'EUR').
        to_currency: Target currency code ('INR', 'AED', 'USD', 'EUR').
        as_of_date: Optional ISO date (YYYY-MM-DD). Uses most recent rate if None.

    Returns:
        JSON with converted_amount, rate, from_currency, to_currency, rate_date, note.
    """
    from_currency = from_currency.upper().strip()
    to_currency   = to_currency.upper().strip()

    if from_currency == to_currency:
        return json.dumps({
            "converted_amount": round(amount, 4),
            "rate": 1.0,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "rate_date": None,
            "note": "Same currency — no conversion needed.",
        })

    with get_conn() as conn, get_cursor(conn) as cur:
        def _fetch_rate(src, dst):
            if as_of_date:
                cur.execute("""
                    SELECT rate, effective_date FROM forex_rates
                    WHERE from_currency=%s AND to_currency=%s AND effective_date<=%s
                    ORDER BY effective_date DESC LIMIT 1
                """, (src, dst, as_of_date))
            else:
                cur.execute("""
                    SELECT rate, effective_date FROM forex_rates
                    WHERE from_currency=%s AND to_currency=%s
                    ORDER BY effective_date DESC LIMIT 1
                """, (src, dst))
            return cur.fetchone()

        row = _fetch_rate(from_currency, to_currency)
        if row:
            rate = float(row["rate"])
        else:
            # Try inverse
            inv = _fetch_rate(to_currency, from_currency)
            if inv:
                rate = round(1 / float(inv["rate"]), 6)
                row  = inv
            else:
                return json.dumps({"error": f"No rate found for {from_currency} → {to_currency}"})

    converted = round(amount * rate, 4)
    return json.dumps({
        "converted_amount": converted,
        "rate": rate,
        "from_currency": from_currency,
        "to_currency": to_currency,
        "rate_date": str(row["effective_date"]),
        "note": f"{amount} {from_currency} = {converted} {to_currency} at rate {rate}",
    })


def find_similar_query(question: str) -> str:
    """
    Search nk_validated_queries for previously validated SQL patterns matching
    the user's question. ALWAYS call this first for any data question.

    Uses pg_trgm trigram similarity (handles typos, word-order variation, synonyms).
    Returns matches with similarity >= 0.3, ranked by similarity then used_count.

    Args:
        question: The user's natural language question.

    Returns:
        JSON with a 'matches' list (up to 3). Each match has:
        question, sql_query, explanation, tables_used, used_count, similarity.
        Returns empty list when no matches found above threshold.
    """
    if not question.strip():
        return json.dumps({"matches": []})

    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute("""
            SELECT question, sql_query, explanation, tables_used, used_count,
                   ROUND(similarity(question, %s)::numeric, 3) AS similarity
            FROM nk_validated_queries
            WHERE similarity(question, %s) >= 0.3
            ORDER BY similarity DESC, used_count DESC
            LIMIT 3
        """, (question, question))
        matches = [dict(r) for r in cur.fetchall()]

    # Fire-and-forget: bump used_count off the critical path
    if matches:
        import threading
        threading.Thread(
            target=_bump_used_count,
            args=(matches[0]["question"],),
            daemon=True,
        ).start()

    return json.dumps({"matches": matches}, default=str)


def _bump_used_count(question: str) -> None:
    """Increment used_count in background — best-effort."""
    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            cur.execute("""
                UPDATE nk_validated_queries
                   SET used_count = used_count + 1, last_used_at = NOW()
                 WHERE question = %s
            """, (question,))
            conn.commit()
    except Exception:
        pass


def save_validated_query(
    question: str,
    sql_query: str,
    explanation: str,
    tables_used: str = "",
) -> str:
    """
    Save a confirmed correct (question, SQL, explanation) tuple to
    nk_validated_queries for future reuse. Call this after a user thumbs-up.

    Args:
        question: The user's original natural language question.
        sql_query: The SQL that correctly answered it.
        explanation: Plain-English explanation including any unit/convention caveats.
        tables_used: Comma-separated table names, e.g. 'mis_monthly,portfolio_companies'.

    Returns:
        Confirmation string.
    """
    with get_conn() as conn, get_cursor(conn) as cur:
        # Fuzzy dedup: skip if a very similar question already exists (>= 0.85 similarity)
        cur.execute("""
            SELECT question, ROUND(similarity(question, %s)::numeric, 3) AS sim
            FROM nk_validated_queries
            WHERE similarity(question, %s) >= 0.85
            ORDER BY sim DESC
            LIMIT 1
        """, (question, question))
        existing = cur.fetchone()
        if existing:
            return (
                f"Very similar pattern already exists (similarity {existing['sim']}): "
                f'"{existing["question"]}" — skipping duplicate.'
            )

        cur.execute("""
            INSERT INTO nk_validated_queries (question, sql_query, explanation, tables_used)
            VALUES (%s, %s, %s, %s)
        """, (question, sql_query, explanation, tables_used))
        conn.commit()

    return "Query pattern saved. Future similar questions will reuse this pattern."
