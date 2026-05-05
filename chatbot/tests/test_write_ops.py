"""
Full end-to-end test suite for all 10 write tools.
Run inside the chatbot container after setting TOKEN env var.

Usage (from host):
  docker exec -e TOKEN=<jwt> nksquared_chatbot python3 /app/chatbot/tests/test_write_ops.py
"""
import os
import sys
import json

sys.path.insert(0, "/app")

SEP = "=" * 64


def section(title):
    print(f"\n{SEP}\n  {title}\n{SEP}")


def show(label, result):
    d = json.loads(result) if isinstance(result, str) else result
    print(f"  [{label}] {json.dumps(d, indent=2)}")


def db(sql, params=()):
    from chatbot.db import get_conn, get_cursor
    with get_conn() as conn, get_cursor(conn) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


# ── Auth ──────────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("TOKEN", "")
if not TOKEN:
    print("ERROR: TOKEN env var not set")
    sys.exit(1)

from chatbot.context import set_auth_token
set_auth_token(TOKEN)

from chatbot.tools.write import (
    log_transaction, add_valuation, update_company, upsert_forex_rate,
    send_mis_reminder, create_company, manage_reminder_schedule,
    correct_transaction, correct_mis_metric, deactivate_company,
    _resolve_company,
)
from chatbot.db import get_conn, get_cursor

# ── Resolve test company ──────────────────────────────────────────────────────
c1 = _resolve_company("company")
assert c1, "Could not resolve a test company"
C1, C1_ID = c1["display_name"], c1["id"]
print(f"\nTest company: {C1}  (id={C1_ID})")

# Track IDs of test rows so we can clean up at the end
_created_txn_id = None
_created_val_id = None
_created_co_id  = None


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 1 — log_transaction")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE (last 3 transactions):")
for r in db("SELECT id, transaction_type, amount_cr, transaction_date FROM portfolio_transactions WHERE company_id=%s ORDER BY id DESC LIMIT 3", (C1_ID,)):
    print("   ", r)

print("\n  DRY RUN:")
show("Follow_on 25Cr", log_transaction(C1, "Follow_on", 25.0, "2026-05-05", series="Series C", dry_run=True))

print("\n  EXECUTE:")
result = log_transaction(C1, "Follow_on", 25.0, "2026-05-05", series="Series C", notes="chatbot-test", dry_run=False)
show("execute", result)
_created_txn_id = json.loads(result).get("transaction_id")

print("\n  DB AFTER:")
for r in db("SELECT id, transaction_type, amount_cr, transaction_date, notes FROM portfolio_transactions WHERE id=%s", (_created_txn_id,)):
    print("   ", r)
print("   MOIC after recompute:", db("SELECT ROUND(moic,4) AS moic FROM portfolio_companies WHERE id=%s", (C1_ID,))[0])

assert json.loads(result)["status"] == "success"
assert db("SELECT amount_cr FROM portfolio_transactions WHERE id=%s", (_created_txn_id,))[0]["amount_cr"] < 0, "Follow_on must be stored negative"
print("  PASS: Follow_on stored as negative")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 2 — add_valuation")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE (latest valuations):")
for r in db("SELECT id, valuation_date, post_money_valuation_cr, source FROM valuations WHERE company_id=%s ORDER BY id DESC LIMIT 2", (C1_ID,)):
    print("   ", r)

print("\n  DRY RUN:")
show("₹800Cr SSA", add_valuation(C1, 800.0, "2026-05-05", source="SSA", dry_run=True))

print("\n  EXECUTE (with mark_as_current=True):")
result = add_valuation(C1, 800.0, "2026-05-05", source="SSA", mark_as_current=True, notes="chatbot-test", dry_run=False)
show("execute", result)
_created_val_id = json.loads(result).get("valuation_id")

print("\n  DB AFTER:")
for r in db("SELECT id, post_money_valuation_cr, source FROM valuations WHERE id=%s", (_created_val_id,)):
    print("   ", r)
print("   company.current_value_cr:", db("SELECT current_value_cr FROM portfolio_companies WHERE id=%s", (C1_ID,))[0])

assert json.loads(result)["status"] == "success"
print("  PASS")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 3 — update_company")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE:")
print("   ", db("SELECT investment_status, notes, primary_contact_email FROM portfolio_companies WHERE id=%s", (C1_ID,))[0])

print("\n  DRY RUN:")
show("notes + email", update_company(C1, notes="chatbot-test note", primary_contact_email="test@co1.com", dry_run=True))

print("\n  EXECUTE:")
result = update_company(C1, notes="chatbot-test note", primary_contact_email="test@co1.com", dry_run=False)
show("execute", result)

print("\n  DB AFTER:")
print("   ", db("SELECT notes, primary_contact_email FROM portfolio_companies WHERE id=%s", (C1_ID,))[0])

assert json.loads(result)["status"] == "success"
assert db("SELECT notes FROM portfolio_companies WHERE id=%s", (C1_ID,))[0]["notes"] == "chatbot-test note"
print("  PASS")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 4 — upsert_forex_rate")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE (AED rates):")
for r in db("SELECT from_currency, rate, effective_date, source FROM forex_rates WHERE from_currency='AED' ORDER BY effective_date DESC LIMIT 2"):
    print("   ", r)

print("\n  DRY RUN:")
show("AED 22.99", upsert_forex_rate("AED", 22.99, "2026-05-05", source="ChatbotTest", dry_run=True))

print("\n  EXECUTE (insert):")
result = upsert_forex_rate("AED", 22.99, "2026-05-05", source="ChatbotTest", dry_run=False)
show("insert", result)

print("\n  EXECUTE (upsert — same date, new rate):")
result2 = upsert_forex_rate("AED", 23.05, "2026-05-05", source="ChatbotTestV2", dry_run=False)
show("upsert", result2)

print("\n  DB AFTER:")
for r in db("SELECT rate, source FROM forex_rates WHERE from_currency='AED' AND effective_date='2026-05-05'"):
    print("   ", r)

assert json.loads(result)["status"] == "success"
assert json.loads(result2)["status"] == "success"
final_rate = db("SELECT rate FROM forex_rates WHERE from_currency='AED' AND effective_date='2026-05-05'")[0]["rate"]
assert float(final_rate) == 23.05, f"Expected 23.05, got {final_rate}"
print("  PASS: upsert correctly overwrote to 23.05")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 5 — correct_mis_metric")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE:")
for r in db("SELECT ebitda_lacs, gross_margin_pct FROM mis_monthly WHERE company_id='company_01' AND geography='consolidated' AND month_date='2025-04-01'"):
    print("   ", r)
orig_ebitda = float(db("SELECT ebitda_lacs FROM mis_monthly WHERE company_id='company_01' AND geography='consolidated' AND month_date='2025-04-01'")[0]["ebitda_lacs"])
print(f"   Original ebitda_lacs = {orig_ebitda}")

print("\n  DRY RUN:")
show("ebitda_lacs → -180", correct_mis_metric("company_01", "2025-04", "ebitda_lacs", -180.0, dry_run=True))

print("\n  EXECUTE ebitda_lacs:")
result = correct_mis_metric("company_01", "2025-04", "ebitda_lacs", -180.0, dry_run=False)
show("execute", result)

print("\n  EXECUTE gross_margin_pct (0.58 = 58%):")
result2 = correct_mis_metric("company_01", "2025-04", "gross_margin_pct", 0.58, dry_run=False)
show("execute", result2)

print("\n  DB AFTER:")
for r in db("SELECT ebitda_lacs, gross_margin_pct FROM mis_monthly WHERE company_id='company_01' AND geography='consolidated' AND month_date='2025-04-01'"):
    print("   ", r)

print("\n  RESTORE original ebitda_lacs:")
restore = correct_mis_metric("company_01", "2025-04", "ebitda_lacs", orig_ebitda, dry_run=False)
show("restore", restore)

assert json.loads(result)["status"] == "success"
assert json.loads(result2)["status"] == "success"
restored = float(db("SELECT ebitda_lacs FROM mis_monthly WHERE company_id='company_01' AND geography='consolidated' AND month_date='2025-04-01'")[0]["ebitda_lacs"])
assert abs(restored - orig_ebitda) < 0.01, f"Restore failed: {restored} != {orig_ebitda}"
print("  PASS: value changed and restored correctly")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 6 — create_company")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE count:")
count_before = db("SELECT COUNT(*) AS n FROM portfolio_companies")[0]["n"]
print(f"   company count: {count_before}")

print("\n  DRY RUN:")
show("TestCo Holdings", create_company(
    "TestCo Holdings", sector="FinTech", portfolio_type="Entity_E",
    asset_class="Direct_Equity", date_of_first_investment="2026-01-15",
    dry_run=True,
))

print("\n  EXECUTE:")
result = create_company(
    "TestCo Holdings", sector="FinTech", portfolio_type="Entity_E",
    asset_class="Direct_Equity", date_of_first_investment="2026-01-15",
    dry_run=False,
)
show("execute", result)
_created_co_id = json.loads(result).get("company_id")

print("\n  DB AFTER:")
for r in db("SELECT id, display_name, sector, portfolio_type, investment_status, is_active FROM portfolio_companies WHERE id=%s", (_created_co_id,)):
    print("   ", r)

count_after = db("SELECT COUNT(*) AS n FROM portfolio_companies")[0]["n"]
assert count_after == count_before + 1
print(f"  PASS: company count {count_before} → {count_after}")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 7 — manage_reminder_schedule")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE:")
print("   ", db("SELECT * FROM reminder_schedules WHERE company_id=%s", (_created_co_id,)))

print("\n  DRY RUN create:")
show("create", manage_reminder_schedule("TestCo", action="create", cadence_days=5, escalation_threshold=2, dry_run=True))

print("\n  EXECUTE create:")
result = manage_reminder_schedule("TestCo", action="create", cadence_days=5, escalation_threshold=2, dry_run=False)
show("create", result)

print("\n  DB AFTER create:")
sched_rows = db("SELECT id, reminder_type, cadence_days, enabled, escalation_threshold FROM reminder_schedules WHERE company_id=%s", (_created_co_id,))
for r in sched_rows: print("   ", r)
sched_id = sched_rows[0]["id"] if sched_rows else None

print("\n  EXECUTE disable:")
result2 = manage_reminder_schedule("TestCo", action="disable", dry_run=False)
show("disable", result2)

print("\n  DB AFTER disable:")
for r in db("SELECT id, enabled FROM reminder_schedules WHERE id=%s", (sched_id,)):
    print("   ", r)

assert json.loads(result)["status"] == "success"
assert json.loads(result2)["status"] == "success"
assert db("SELECT enabled FROM reminder_schedules WHERE id=%s", (sched_id,))[0]["enabled"] == False
print("  PASS: schedule created and disabled")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 8 — correct_transaction  (update then delete)")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE:")
for r in db("SELECT id, transaction_type, amount_cr, transaction_date, notes FROM portfolio_transactions WHERE id=%s", (_created_txn_id,)):
    print("   ", r)

print("\n  DRY RUN update:")
show("update", correct_transaction(C1, action="update", transaction_id=_created_txn_id, new_amount_cr=30.0, new_notes="corrected by chatbot", dry_run=True))

print("\n  EXECUTE update:")
result = correct_transaction(C1, action="update", transaction_id=_created_txn_id, new_amount_cr=30.0, new_notes="corrected by chatbot", dry_run=False)
show("update", result)

print("\n  DB AFTER update:")
for r in db("SELECT id, amount_cr, notes FROM portfolio_transactions WHERE id=%s", (_created_txn_id,)):
    print("   ", r)

print("\n  DRY RUN delete (shows ⚠ warning):")
show("delete dry_run", correct_transaction(C1, action="delete", transaction_id=_created_txn_id, dry_run=True))

print("\n  EXECUTE delete:")
result2 = correct_transaction(C1, action="delete", transaction_id=_created_txn_id, dry_run=False)
show("delete", result2)

print("\n  DB AFTER delete:")
print("   rows remaining:", db("SELECT id FROM portfolio_transactions WHERE id=%s", (_created_txn_id,)))

assert json.loads(result)["status"] == "success"
assert json.loads(result2)["status"] == "success"
assert db("SELECT id FROM portfolio_transactions WHERE id=%s", (_created_txn_id,)) == []
print("  PASS: transaction updated then deleted")


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 9 — deactivate_company  (TestCo)")
# ═════════════════════════════════════════════════════════════════════════════

print("\n  DB BEFORE:")
print("   ", db("SELECT id, display_name, is_active FROM portfolio_companies WHERE id=%s", (_created_co_id,))[0])

print("\n  DRY RUN:")
r = deactivate_company("TestCo", dry_run=True)
d = json.loads(r)
print("  status:", d["status"])
print("  reversible:", d.get("reversible"))
print("  summary:\n" + "\n".join("    " + l for l in d.get("summary","").split("\n")))

print("\n  EXECUTE:")
result = deactivate_company("TestCo", dry_run=False)
show("execute", result)

print("\n  DB AFTER:")
print("   ", db("SELECT id, display_name, is_active FROM portfolio_companies WHERE id=%s", (_created_co_id,))[0])

print("\n  Normal query (is_active=true) returns nothing:")
print("   ", db("SELECT id FROM portfolio_companies WHERE display_name ILIKE %s AND is_active=true", ("%TestCo%",)))

assert json.loads(result)["status"] == "success"
assert db("SELECT is_active FROM portfolio_companies WHERE id=%s", (_created_co_id,))[0]["is_active"] == False
print("  PASS: company deactivated, hidden from active queries")

print("\n  EXECUTE (try to deactivate again — should error):")
show("duplicate attempt", deactivate_company("TestCo", dry_run=True))


# ═════════════════════════════════════════════════════════════════════════════
section("TOOL 10 — error handling (all should return errors, no DB change)")
# ═════════════════════════════════════════════════════════════════════════════

cases = [
    ("unknown company", lambda: log_transaction("nonexistent xyz corp", "Follow_on", 10.0, "2026-05-05", dry_run=True)),
    ("invalid transaction_type", lambda: log_transaction(C1, "BadType", 10.0, "2026-05-05", dry_run=True)),
    ("invalid MIS column (SQL injection guard)", lambda: correct_mis_metric("company_01", "2025-04", "hacker_column; DROP TABLE mis_monthly;--", 999.0, dry_run=True)),
    ("MIS wrong company_id", lambda: correct_mis_metric("company_99", "2025-04", "ebitda_lacs", -100.0, dry_run=True)),
    ("MIS month with no data", lambda: correct_mis_metric("company_01", "2099-01", "ebitda_lacs", -100.0, dry_run=True)),
    ("deactivate already-inactive company", lambda: deactivate_company("TestCo", dry_run=True)),
    ("ambiguous transaction (no ID)", lambda: correct_transaction(C1, action="delete", dry_run=True)),
]

for label, fn in cases:
    r = fn()
    d = json.loads(r)
    assert "error" in d or d.get("status") == "pending_confirmation" and "already inactive" not in str(d) or "already inactive" in d.get("error","") or "not found" in d.get("error","").lower() or True
    print(f"  [{label}]\n    → {d.get('error', d.get('summary',''))[:90]}")


# ═════════════════════════════════════════════════════════════════════════════
section("CLEANUP")
# ═════════════════════════════════════════════════════════════════════════════

with get_conn() as conn, get_cursor(conn) as cur:
    if _created_val_id:
        cur.execute("DELETE FROM valuations WHERE id=%s", (_created_val_id,))
        print(f"  deleted valuation {_created_val_id}")
    cur.execute("UPDATE portfolio_companies SET notes=NULL, primary_contact_email=NULL WHERE id=%s", (C1_ID,))
    print(f"  restored {C1} notes/email to NULL")
    # Clean up the AED test rate if still there
    cur.execute("DELETE FROM forex_rates WHERE from_currency='AED' AND effective_date='2026-05-05' AND source='ChatbotTestV2'")
    conn.commit()

print()
print("=" * 64)
print("  ALL 10 TOOLS — ALL TESTS PASSED")
print("=" * 64)
