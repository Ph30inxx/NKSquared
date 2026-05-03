"""
Tests for chatbot/schema_loader.py.

All tests connect to the real PostgreSQL instance.
No mocking — cache behaviour is verified through object identity and timing.
"""
from __future__ import annotations

import threading
import time

import pytest

from chatbot.schema_loader import (
    CHATBOT_TABLES,
    invalidate_schema_cache,
    load_schema_context,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the module-level cache before and after every test in this file."""
    invalidate_schema_cache()
    yield
    invalidate_schema_cache()


# ── Basic smoke ───────────────────────────────────────────────────────────────

def test_returns_non_empty_string(pg):
    result = load_schema_context()
    assert isinstance(result, str)
    assert len(result) > 100


def test_contains_schema_header(pg):
    result = load_schema_context()
    assert "SCHEMA" in result.upper() or "TABLE" in result.upper()


# ── Table coverage ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("table_name", CHATBOT_TABLES)
def test_each_chatbot_table_appears_in_output(pg, table_name):
    result = load_schema_context()
    assert table_name in result, f"Table '{table_name}' not found in schema context"


# ── Critical column coverage ──────────────────────────────────────────────────

@pytest.mark.parametrize("column", [
    "investment_value_cr",
    "current_value_cr",
    "moic",
    "amount_inr_cr",
    "transaction_type",
    "ebitda_lacs",
    "gross_margin_pct",
    "geography",
    "company_id",
    "effective_date",
])
def test_critical_column_appears_in_output(pg, column):
    result = load_schema_context()
    assert column in result, f"Column '{column}' not found in schema context"


# ── Constraint markers ────────────────────────────────────────────────────────

def test_pk_marker_present(pg):
    result = load_schema_context()
    assert "PK" in result


def test_fk_marker_present(pg):
    # portfolio_transactions has a FK to portfolio_companies
    result = load_schema_context()
    assert "FK" in result


# ── Caching — verified by object identity and timing (no mocks) ───────────────

def test_second_call_returns_same_object(pg):
    """Cache hit returns the exact same Python string object."""
    first  = load_schema_context()
    second = load_schema_context()
    assert first is second


def test_cached_call_is_significantly_faster_than_db_call(pg):
    """
    The first call hits PostgreSQL (takes measurable time).
    The second call reads from the module-level cache and completes in < 1 ms.
    """
    t0 = time.perf_counter()
    load_schema_context()
    first_elapsed = time.perf_counter() - t0

    t1 = time.perf_counter()
    load_schema_context()
    cached_elapsed = time.perf_counter() - t1

    assert cached_elapsed < 0.001, (
        f"Cached call took {cached_elapsed:.4f}s — expected < 0.001s"
    )
    assert cached_elapsed < first_elapsed / 10, (
        f"Cache should be at least 10× faster than DB call "
        f"(DB: {first_elapsed:.4f}s, cached: {cached_elapsed:.4f}s)"
    )


# ── Invalidation ──────────────────────────────────────────────────────────────

def test_invalidate_clears_cache_content_stays_same(pg):
    """Invalidating and reloading gives identical content from the DB."""
    first = load_schema_context()
    invalidate_schema_cache()
    second = load_schema_context()
    assert first == second


def test_invalidate_produces_new_object(pg):
    """After invalidation the next call creates a fresh string object (re-fetched from DB)."""
    first = load_schema_context()
    invalidate_schema_cache()
    second = load_schema_context()
    # Same content but a different Python object — proves the cache was cleared and rebuilt
    assert first is not second


def test_invalidate_then_second_call_is_slower_than_pure_cache(pg):
    """After invalidation the next call must hit the DB again (measurably slower than cache)."""
    load_schema_context()   # warm up cache

    # Measure a pure cache hit
    t0 = time.perf_counter()
    load_schema_context()
    cached_elapsed = time.perf_counter() - t0

    # Invalidate and measure the forced DB reload
    invalidate_schema_cache()
    t1 = time.perf_counter()
    load_schema_context()
    reload_elapsed = time.perf_counter() - t1

    assert reload_elapsed > cached_elapsed, (
        "Reloading after invalidation should be slower than a cache hit "
        f"(reload: {reload_elapsed:.4f}s, cache: {cached_elapsed:.4f}s)"
    )


# ── Thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_calls_return_same_content(pg):
    """
    Six threads call load_schema_context() simultaneously.
    All should receive the identical string with no exceptions.
    """
    results: list[str] = []
    errors:  list[Exception] = []

    def _call():
        try:
            results.append(load_schema_context())
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_call) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Threads raised exceptions: {errors}"
    assert len(results) == 6
    assert all(r == results[0] for r in results)


def test_concurrent_calls_only_one_hits_db(pg):
    """
    After all six threads finish the cache holds a single object —
    confirming the lock prevented duplicate DB calls.
    """
    results: list[str] = []

    def _call():
        results.append(load_schema_context())

    threads = [threading.Thread(target=_call) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 6 results must be the exact same Python object
    first_id = id(results[0])
    assert all(id(r) == first_id for r in results), (
        "Not all threads received the same cached object — "
        "the lock may not be preventing duplicate DB calls"
    )


# ── Integration with prompts ──────────────────────────────────────────────────

def test_get_analyst_prompt_contains_live_schema(pg):
    """The assembled analyst prompt includes real table names from PostgreSQL."""
    from chatbot.prompts import get_analyst_prompt, invalidate_prompt_cache
    invalidate_prompt_cache()

    prompt = get_analyst_prompt()
    assert isinstance(prompt, str)
    assert "portfolio_companies" in prompt
    assert "mis_monthly"         in prompt
    assert "ebitda_lacs"         in prompt


def test_get_analyst_prompt_is_cached(pg):
    from chatbot.prompts import get_analyst_prompt, invalidate_prompt_cache
    invalidate_prompt_cache()

    first  = get_analyst_prompt()
    second = get_analyst_prompt()
    assert first is second


def test_invalidate_prompt_cache_triggers_reload(pg):
    from chatbot.prompts import get_analyst_prompt, invalidate_prompt_cache
    invalidate_prompt_cache()

    first = get_analyst_prompt()
    invalidate_prompt_cache()
    second = get_analyst_prompt()

    assert first == second       # identical content from the same DB
    assert first is not second   # but a newly built string object
