"""
Dynamically build a schema context string by querying PostgreSQL's
information_schema. Cached after the first call — restart the service
to pick up schema changes.
"""
from __future__ import annotations

import threading
from collections import defaultdict

from chatbot.db import get_conn, get_cursor

# Tables the chatbot is allowed to query (drives the schema snapshot)
CHATBOT_TABLES = [
    "portfolio_companies",
    "portfolio_transactions",
    "valuations",
    "forex_rates",
    "mis_monthly",
    "mis_bu_monthly",
    "mis_outlet_monthly",
    "mis_submissions",
    "mis_anomalies",
    "portfolio_categories",
    "nk_validated_queries",
    "portfolio_aggregates_mv",
]

_cache: str | None = None
_lock  = threading.Lock()


def _fmt_type(data_type: str, char_max: int | None, num_prec: int | None, num_scale: int | None) -> str:
    """Produce a compact, human-readable type string."""
    if data_type == "character varying":
        return f"varchar({char_max})" if char_max else "varchar"
    if data_type == "numeric":
        if num_prec is not None and num_scale is not None:
            return f"numeric({num_prec},{num_scale})"
        return "numeric"
    if data_type == "timestamp with time zone":
        return "timestamptz"
    if data_type == "timestamp without time zone":
        return "timestamp"
    return data_type  # integer, boolean, text, date, etc. — already concise


def _load_from_db() -> str:
    with get_conn() as conn, get_cursor(conn) as cur:
        # ── Columns ──────────────────────────────────────────────────────────
        cur.execute("""
            SELECT
                table_name,
                column_name,
                data_type,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable,
                column_default,
                ordinal_position
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = ANY(%s)
            ORDER BY table_name, ordinal_position
        """, (CHATBOT_TABLES,))
        col_rows = cur.fetchall()

        # ── Constraints (PK, FK, UNIQUE) ──────────────────────────────────
        cur.execute("""
            SELECT
                tc.table_name,
                tc.constraint_type,
                kcu.column_name,
                ccu.table_name  AS ref_table,
                ccu.column_name AS ref_column
            FROM information_schema.table_constraints      tc
            JOIN information_schema.key_column_usage       kcu
                ON  tc.constraint_name  = kcu.constraint_name
                AND tc.table_schema     = kcu.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON  tc.constraint_name  = ccu.constraint_name
                AND tc.table_schema     = ccu.table_schema
            WHERE tc.table_schema  = 'public'
              AND tc.table_name    = ANY(%s)
              AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY', 'UNIQUE')
            ORDER BY tc.table_name, tc.constraint_type, kcu.column_name
        """, (CHATBOT_TABLES,))
        con_rows = cur.fetchall()

    # ── Group columns by table ────────────────────────────────────────────────
    tables: dict[str, list] = defaultdict(list)
    for r in col_rows:
        tables[r["table_name"]].append(r)

    # ── Group constraints by table ────────────────────────────────────────────
    pk_cols:     dict[str, list[str]]           = defaultdict(list)
    fk_cols:     dict[str, list[tuple]]         = defaultdict(list)
    unique_cols: dict[str, list[str]]           = defaultdict(list)

    for r in con_rows:
        tbl = r["table_name"]
        if r["constraint_type"] == "PRIMARY KEY":
            pk_cols[tbl].append(r["column_name"])
        elif r["constraint_type"] == "FOREIGN KEY":
            fk_cols[tbl].append((r["column_name"], r["ref_table"], r["ref_column"]))
        elif r["constraint_type"] == "UNIQUE":
            unique_cols[tbl].append(r["column_name"])

    # ── Format output ─────────────────────────────────────────────────────────
    lines: list[str] = ["=== LIVE DATABASE SCHEMA (auto-loaded from PostgreSQL) ===\n"]

    for table_name in CHATBOT_TABLES:
        if table_name not in tables:
            continue  # table doesn't exist yet (e.g. before migration runs)

        lines.append(f"TABLE: {table_name}")

        for col in tables[table_name]:
            col_name  = col["column_name"]
            type_str  = _fmt_type(
                col["data_type"],
                col["character_maximum_length"],
                col["numeric_precision"],
                col["numeric_scale"],
            )
            nullable  = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"

            # Build annotation tags: [PK], [FK → table.col], [DEFAULT x]
            tags: list[str] = []
            if col_name in pk_cols.get(table_name, []):
                tags.append("PK")
            for fk_col, ref_tbl, ref_col in fk_cols.get(table_name, []):
                if fk_col == col_name:
                    tags.append(f"FK → {ref_tbl}.{ref_col}")
            if col["column_default"] and "nextval" not in col["column_default"]:
                # skip sequence defaults (noise), keep meaningful defaults
                default_val = col["column_default"].replace("::character varying", "").strip("'")
                tags.append(f"default={default_val}")

            tag_str = f"  [{', '.join(tags)}]" if tags else ""
            lines.append(f"  {col_name:<30} {type_str:<20} {nullable}{tag_str}")

        # Unique constraints
        if unique_cols.get(table_name):
            lines.append(f"  UNIQUE: ({', '.join(unique_cols[table_name])})")

        lines.append("")  # blank line between tables

    return "\n".join(lines)


def load_schema_context() -> str:
    """
    Return the schema context string, loading from PostgreSQL on first call
    and returning the cached value on all subsequent calls.

    Thread-safe — safe to call from multiple concurrent requests.
    """
    global _cache
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is None:   # re-check inside lock
            _cache = _load_from_db()
    return _cache


def invalidate_schema_cache() -> None:
    """Force a fresh DB load on the next call. Useful after migrations."""
    global _cache
    with _lock:
        _cache = None
