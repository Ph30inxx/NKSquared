"""
Write tools for the NKSquared Analyst agent.

All tools follow a two-step confirmation pattern:
  1. dry_run=True  (default) — validate inputs, resolve IDs, return a plain-English
                               summary of what WILL happen. Nothing is written.
  2. dry_run=False           — execute the operation after the user says "yes".

Tools 1-8 call the existing FastAPI backend (/api/v1/...) over HTTP, forwarding
the analyst's JWT token so all business logic, MOIC recomputation, and audit
logging runs through the normal backend service layer.

Tool 9  (correct_mis_metric)  writes directly via psycopg2 — the MIS router has
no row-level PATCH endpoint, and MIS tables have no post-write triggers.

Tool 10 (deactivate_company)  calls DELETE /companies/{id} which soft-deletes
(sets is_active=False) — all historical data is preserved.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import httpx

from chatbot.config import BACKEND_API_URL
from chatbot.context import get_auth_token, is_voice_mode
from chatbot.db import get_conn, get_cursor

logger = logging.getLogger("nk.chatbot.write")


def _voice_dry_run(dry_run: bool) -> bool:
    """In voice mode, always execute (skip preview) since Vapi already confirmed."""
    if is_voice_mode():
        return False
    return dry_run

# ── Shared helpers ────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    token = get_auth_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


def _resolve_company(name: str) -> dict | None:
    """
    Resolve a partial company name to its full backend record.
    Returns the first active match or None.
    """
    try:
        resp = httpx.get(
            f"{BACKEND_API_URL}/companies",
            params={"q": name, "limit": 5, "include_inactive": False},
            headers=_headers(),
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return items[0] if items else None
    except Exception as exc:
        logger.warning("_resolve_company error: %s", exc)
        return None


def _err(msg: str) -> str:
    return json.dumps({"error": msg})


# ── Tool 1: log_transaction ───────────────────────────────────────────────────

def log_transaction(
    company_name: str,
    transaction_type: str,
    amount_cr: float,
    transaction_date: str,
    original_currency: str = "INR",
    series: str = None,
    instrument_type: str = None,
    investing_entity: str = None,
    notes: str = None,
    dry_run: bool = True,
) -> str:
    """
    Log a portfolio transaction for a company.

    Use dry_run=True to preview the changes, then dry_run=False to execute.

    Args:
        company_name: Display name or partial name (case-insensitive match).
        transaction_type: One of 'Investment', 'Follow_on', 'Partial_exit',
            'Full_exit', 'Distribution', 'Write_down', 'Write_off'.
        amount_cr: Amount in INR Crores. Sign is enforced automatically:
            Investment/Follow_on → stored negative (outflow).
            Partial_exit/Full_exit/Distribution → stored positive (inflow).
            Write_down/Write_off → stored as 0 (no cash flow).
        transaction_date: ISO date YYYY-MM-DD.
        original_currency: Source currency if not INR (e.g. 'AED', 'USD').
        series: Funding round label e.g. 'Series B'. Optional.
        instrument_type: 'CCPS', 'CCD', 'Equity', 'Convertible Note'. Optional.
        investing_entity: Which NKSquared entity is investing. Optional.
        notes: Free-text notes. Optional.
        dry_run: True = preview only. False = execute.
    """
    ZERO  = {"Write_down", "Write_off"}
    VALID = ZERO | {"Investment", "Follow_on", "Partial_exit", "Full_exit", "Distribution"}

    if transaction_type not in VALID:
        return _err(f"Invalid transaction_type '{transaction_type}'. Valid: {sorted(VALID)}")

    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'. Check the name and try again.")

    # Backend schema uses `amount` (always non-negative; backend applies the sign
    # based on transaction_type). Write_down/Write_off have no cash flow so 0.
    magnitude = 0.0 if transaction_type in ZERO else abs(amount_cr)

    summary = (
        f"Log {transaction_type} of ₹{magnitude:.2f} Cr "
        f"for {company['display_name']} on {transaction_date}"
    )
    if series:
        summary += f" | series: {series}"
    if original_currency != "INR":
        summary += f" | original currency: {original_currency}"

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({
            "status": "pending_confirmation",
            "summary": summary,
            "company": company["display_name"],
            "company_id": company["id"],
        })

    # `amount` field in TransactionCreate — always non-negative
    payload = {
        "transaction_type": transaction_type,
        "amount": magnitude,
        "transaction_date": transaction_date,
        "original_currency": original_currency,
    }
    for k, v in [("series", series), ("instrument_type", instrument_type),
                 ("investing_entity", investing_entity), ("notes", notes)]:
        if v:
            payload[k] = v
    if original_currency != "INR":
        payload["original_amount"] = magnitude

    try:
        resp = httpx.post(
            f"{BACKEND_API_URL}/companies/{company['id']}/transactions",
            json=payload, headers=_headers(), timeout=15,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code == 201:
        row = resp.json()
        return json.dumps({
            "status": "success",
            "message": f"{transaction_type} logged for {company['display_name']}. "
                       f"Transaction ID: {row['id']}. MOIC has been recomputed.",
            "transaction_id": row["id"],
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 2: add_valuation ─────────────────────────────────────────────────────

def add_valuation(
    company_name: str,
    post_money_valuation_cr: float,
    valuation_date: str,
    source: str = "Internal",
    pre_money_valuation_cr: float = None,
    notes: str = None,
    mark_as_current: bool = False,
    dry_run: bool = True,
) -> str:
    """
    Add a new valuation record for a portfolio company.

    Use dry_run=True to preview, then dry_run=False to execute.

    Args:
        company_name: Company name (partial match).
        post_money_valuation_cr: Post-money valuation in INR Crores.
        valuation_date: ISO date YYYY-MM-DD. Use today if not specified by user.
        source: 'SSA', '409A', 'Internal', 'Secondary', or 'Audit'. Default 'Internal'.
        pre_money_valuation_cr: Optional.
        notes: Optional context.
        mark_as_current: If True also updates company.current_value_cr with
                         this valuation's post-money figure.
        dry_run: True = preview. False = execute.
    """
    VALID_SRC = {"SSA", "409A", "Internal", "Secondary", "Audit"}
    if source not in VALID_SRC:
        return _err(f"Invalid source '{source}'. Valid: {sorted(VALID_SRC)}")

    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    summary = (
        f"Add {source} valuation of ₹{post_money_valuation_cr:.2f} Cr (post-money) "
        f"for {company['display_name']} as of {valuation_date}"
    )
    if mark_as_current:
        summary += " — and set as current company value"

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({"status": "pending_confirmation", "summary": summary,
                           "company": company["display_name"]})

    payload: dict = {
        "post_money_valuation_cr": post_money_valuation_cr,
        "valuation_date": valuation_date,
        "source": source,
    }
    if pre_money_valuation_cr is not None:
        payload["pre_money_valuation_cr"] = pre_money_valuation_cr
    if notes:
        payload["notes"] = notes

    try:
        resp = httpx.post(
            f"{BACKEND_API_URL}/companies/{company['id']}/valuations",
            json=payload, headers=_headers(), timeout=15,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code != 201:
        return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")

    row = resp.json()
    result_msg = f"Valuation added for {company['display_name']}. ID: {row['id']}."

    if mark_as_current:
        try:
            mc = httpx.post(
                f"{BACKEND_API_URL}/companies/{company['id']}/mark-current",
                json={"valuation_id": row["id"]},
                headers=_headers(), timeout=15,
            )
            result_msg += " Set as current company value." if mc.status_code == 200 \
                else " (Warning: could not set as current value.)"
        except Exception:
            result_msg += " (Warning: mark-current call failed.)"

    return json.dumps({"status": "success", "message": result_msg, "valuation_id": row["id"]})


# ── Tool 3: update_company ────────────────────────────────────────────────────

def update_company(
    company_name: str,
    display_name: str = None,
    sector: str = None,
    sub_sector: str = None,
    portfolio_type: str = None,
    asset_class: str = None,
    country: str = None,
    date_of_first_investment: str = None,
    currency: str = None,
    current_value_cr: float = None,
    investment_status: str = None,
    portfolio_status: str = None,
    notes: str = None,
    primary_contact_email: str = None,
    escalation_contact_email: str = None,
    reporting_frequency: str = None,
    dry_run: bool = True,
) -> str:
    """
    Update fields on an existing portfolio company record.

    Use for: updating current value (mark-to-market), changing investment status,
    renaming display name, updating sector/sub-sector, portfolio type, asset class,
    country, date of first investment, currency, notes, or contact emails.

    Use dry_run=True to preview current vs proposed values.

    Args:
        company_name: Company name (partial match).
        display_name: Short display name shown in dashboards.
        sector: Industry sector (e.g. 'FinTech', 'Consumer', 'Real Estate').
        sub_sector: Sub-sector classification.
        portfolio_type: One of 'Entity_D_Core', 'Entity_D_Non_Core', 'Entity_D_LLC',
                        'Entity_E', 'Entity_A', 'Strategic_Equity', 'Entity_C',
                        'Real_Estate_Debt'.
        asset_class: 'Direct_Equity', 'Fund_Investment', or 'Debt_Instrument'.
        country: Country of operation (e.g. 'India', 'UAE').
        date_of_first_investment: ISO date YYYY-MM-DD of first capital deployment.
        currency: Reporting currency (e.g. 'INR', 'AED', 'USD').
        current_value_cr: Updated market value in INR Crores.
        investment_status: 'Active','Written_off','Exit_via_IPO',
                           'Exit_via_Share_swap','Matured'.
        portfolio_status: 'Unrealized' or 'Realized'.
        notes: Free-text notes (replaces existing notes).
        primary_contact_email: Contact email for MIS reminders.
        escalation_contact_email: Escalation contact email.
        reporting_frequency: 'Monthly', 'Quarterly', etc.
        dry_run: True = preview. False = execute.
    """
    VALID_INV = {"Active", "Written_off", "Exit_via_IPO", "Exit_via_Share_swap", "Matured"}
    VALID_PORT = {"Unrealized", "Realized"}
    VALID_TYPES = {
        "Entity_D_Core", "Entity_D_Non_Core", "Entity_D_LLC", "Entity_E",
        "Entity_A", "Strategic_Equity", "Entity_C", "Real_Estate_Debt",
    }
    VALID_ASSET = {"Direct_Equity", "Fund_Investment", "Debt_Instrument"}

    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    updates: dict = {}
    changes: list[str] = []

    if display_name is not None:
        updates["display_name"] = display_name
        changes.append(f"display name → {display_name}")
    if sector is not None:
        updates["sector"] = sector
        changes.append(f"sector → {sector}")
    if sub_sector is not None:
        updates["sub_sector"] = sub_sector
        changes.append(f"sub-sector → {sub_sector}")
    if portfolio_type is not None:
        if portfolio_type and portfolio_type not in VALID_TYPES:
            return _err(f"Invalid portfolio_type. Valid: {sorted(VALID_TYPES)}")
        updates["portfolio_type"] = portfolio_type
        changes.append(f"portfolio type → {portfolio_type}")
    if asset_class is not None:
        if asset_class and asset_class not in VALID_ASSET:
            return _err(f"Invalid asset_class. Valid: {sorted(VALID_ASSET)}")
        updates["asset_class"] = asset_class
        changes.append(f"asset class → {asset_class}")
    if country is not None:
        updates["country"] = country
        changes.append(f"country → {country}")
    if date_of_first_investment is not None:
        updates["date_of_first_investment"] = date_of_first_investment
        changes.append(f"date of first investment → {date_of_first_investment}")
    if currency is not None:
        updates["currency"] = currency
        changes.append(f"currency → {currency}")
    if current_value_cr is not None:
        updates["current_value_cr"] = current_value_cr
        changes.append(f"current value → ₹{current_value_cr:.2f} Cr")
    if investment_status:
        if investment_status not in VALID_INV:
            return _err(f"Invalid investment_status. Valid: {sorted(VALID_INV)}")
        updates["investment_status"] = investment_status
        changes.append(f"investment status → {investment_status}")
    if portfolio_status:
        if portfolio_status not in VALID_PORT:
            return _err(f"Invalid portfolio_status. Valid: {sorted(VALID_PORT)}")
        updates["portfolio_status"] = portfolio_status
        changes.append(f"portfolio status → {portfolio_status}")
    if notes is not None:
        updates["notes"] = notes
        changes.append("notes updated")
    if primary_contact_email:
        updates["primary_contact_email"] = primary_contact_email
        changes.append(f"primary contact email → {primary_contact_email}")
    if escalation_contact_email:
        updates["escalation_contact_email"] = escalation_contact_email
        changes.append(f"escalation email → {escalation_contact_email}")
    if reporting_frequency:
        updates["reporting_frequency"] = reporting_frequency
        changes.append(f"reporting frequency → {reporting_frequency}")

    if not updates:
        return _err("No fields to update. Provide at least one value to change.")

    summary = f"Update {company['display_name']}: {'; '.join(changes)}"

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({
            "status": "pending_confirmation",
            "summary": summary,
            "company": company["display_name"],
            "current_values": {
                "display_name": company.get("display_name"),
                "sector": company.get("sector"),
                "sub_sector": company.get("sub_sector"),
                "portfolio_type": company.get("portfolio_type"),
                "asset_class": company.get("asset_class"),
                "country": company.get("country"),
                "date_of_first_investment": company.get("date_of_first_investment"),
                "currency": company.get("currency"),
                "current_value_cr": company.get("current_value_cr"),
                "investment_status": company.get("investment_status"),
                "portfolio_status": company.get("portfolio_status"),
            },
        })

    try:
        resp = httpx.patch(
            f"{BACKEND_API_URL}/companies/{company['id']}",
            json=updates, headers=_headers(), timeout=15,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code == 200:
        return json.dumps({
            "status": "success",
            "message": f"{company['display_name']} updated. {'; '.join(changes)}.",
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 4: upsert_forex_rate ─────────────────────────────────────────────────

def upsert_forex_rate(
    from_currency: str,
    rate: float,
    effective_date: str,
    to_currency: str = "INR",
    source: str = None,
    dry_run: bool = True,
) -> str:
    """
    Add or update a foreign exchange rate.

    If a rate already exists for (effective_date, from_currency, to_currency)
    it is overwritten (upsert). Use when an analyst receives a new FX rate.

    Use dry_run=True to preview, then dry_run=False to execute.

    Args:
        from_currency: Source currency ('AED', 'USD', 'EUR').
        rate: Exchange rate value (e.g. 22.85 for AED→INR).
        effective_date: Date the rate applies (YYYY-MM-DD).
        to_currency: Target currency. Default 'INR'.
        source: Optional label e.g. 'Bloomberg', 'Manual'.
        dry_run: True = preview. False = execute.
    """
    from_currency = from_currency.upper().strip()
    to_currency   = to_currency.upper().strip()

    summary = f"Set {from_currency} → {to_currency} = {rate} effective {effective_date}"
    if source:
        summary += f" (source: {source})"

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({"status": "pending_confirmation", "summary": summary})

    payload: dict = {
        "from_currency": from_currency,
        "to_currency":   to_currency,
        "rate":          rate,
        "effective_date": effective_date,
    }
    if source:
        payload["source"] = source

    try:
        resp = httpx.post(
            f"{BACKEND_API_URL}/forex-rates",
            json=payload, headers=_headers(), timeout=10,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code in (200, 201):
        return json.dumps({
            "status": "success",
            "message": f"{from_currency} → {to_currency} rate set to {rate} for {effective_date}.",
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 5: send_mis_reminder ─────────────────────────────────────────────────

def send_mis_reminder(
    company_name: str,
    is_escalation: bool = False,
    dry_run: bool = True,
) -> str:
    """
    Send an MIS submission reminder to a portfolio company immediately,
    outside the normal scheduled cadence.

    The company must have a ReminderSchedule configured and a
    primary_contact_email set. Standard reminder goes to primary_contact_email.
    Escalation goes to escalation_contact_email and CC's primary_contact_email.

    Use dry_run=True to preview exactly who will be emailed.

    Args:
        company_name: Company name (partial match).
        is_escalation: True to send as an escalation to the senior contact.
        dry_run: True = preview. False = execute.
    """
    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    primary_email = company.get("primary_contact_email")
    if not primary_email:
        return _err(
            f"{company['display_name']} has no primary_contact_email set. "
            "Update the company record first using update_company."
        )

    # Verify a ReminderSchedule exists — backend requires one for send-now
    schedule_info: dict | None = None
    try:
        sr = httpx.get(
            f"{BACKEND_API_URL}/reminders/schedules",
            params={"company_id": company["id"]},
            headers=_headers(),
            timeout=10,
        )
        if sr.status_code == 200:
            schedules = sr.json()
            schedule_info = schedules[0] if schedules else None
    except Exception as exc:
        logger.warning("Could not fetch schedules for pre-check: %s", exc)

    if schedule_info is None:
        return _err(
            f"{company['display_name']} has no reminder schedule configured. "
            "Create one first using manage_reminder_schedule."
        )

    escalation_email = company.get("escalation_contact_email")
    kind = "escalation reminder" if is_escalation else "MIS reminder"

    if is_escalation:
        if escalation_email:
            summary = (
                f"Send {kind} for {company['display_name']}: "
                f"email → {escalation_email} (CC: {primary_email})"
            )
        else:
            summary = (
                f"Send {kind} for {company['display_name']}: "
                f"no escalation_contact_email set — will fall back to primary ({primary_email})"
            )
    else:
        summary = (
            f"Send {kind} for {company['display_name']}: "
            f"email → {primary_email}"
        )

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({
            "status": "pending_confirmation",
            "summary": summary,
            "company": company["display_name"],
            "to": escalation_email if (is_escalation and escalation_email) else primary_email,
            "cc": primary_email if (is_escalation and escalation_email) else None,
            "schedule": {
                "reminder_type": schedule_info.get("reminder_type"),
                "cadence_days": schedule_info.get("cadence_days"),
                "enabled": schedule_info.get("enabled"),
            },
        })

    try:
        resp = httpx.post(
            f"{BACKEND_API_URL}/reminders/companies/{company['id']}/send-now",
            json={"is_escalation": is_escalation},
            headers=_headers(), timeout=20,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code == 200:
        log = resp.json()
        return json.dumps({
            "status": "success",
            "message": (
                f"{kind.capitalize()} sent to {company['display_name']}. "
                f"Recipient: {log.get('recipient_email')}. "
                f"Period: {log.get('related_period', 'N/A')}."
            ),
            "log_id": log.get("id"),
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 6: create_company ────────────────────────────────────────────────────

def create_company(
    company_name: str,
    display_name: str = None,
    sector: str = None,
    portfolio_type: str = None,
    asset_class: str = None,
    investment_status: str = "Active",
    date_of_first_investment: str = None,
    country: str = "India",
    currency: str = "INR",
    notes: str = None,
    primary_contact_email: str = None,
    dry_run: bool = True,
) -> str:
    """
    Create a new portfolio company record.

    Only company_name is required. All other fields can be filled in later
    via update_company.

    Use dry_run=True to preview. Note: dry_run=False creates a new DB row.

    Args:
        company_name: Legal company name.
        display_name: Short name for dashboards. Defaults to company_name.
        sector: Industry sector (e.g. 'FinTech', 'Consumer', 'Real Estate').
        portfolio_type: One of 'Entity_D_Core', 'Entity_D_Non_Core',
            'Entity_D_LLC', 'Entity_E', 'Entity_A', 'Strategic_Equity',
            'Entity_C', 'Real_Estate_Debt'.
        asset_class: 'Direct_Equity', 'Fund_Investment', or 'Debt_Instrument'.
        investment_status: Default 'Active'.
        date_of_first_investment: ISO date of first capital deployment.
        country: Country of operation. Default 'India'.
        currency: Reporting currency. Default 'INR'.
        notes: Free-text notes.
        primary_contact_email: MIS contact email.
        dry_run: True = preview. False = execute.
    """
    dn = display_name or company_name
    summary = f"Create new portfolio company: {dn}"
    if sector:
        summary += f" | sector: {sector}"
    if portfolio_type:
        summary += f" | type: {portfolio_type}"
    if date_of_first_investment:
        summary += f" | first investment: {date_of_first_investment}"

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({"status": "pending_confirmation", "summary": summary})

    payload: dict = {
        "company_name": company_name,
        "display_name": display_name or company_name,   # always set; backend requires it
        "investment_status": investment_status,
        "country": country,
        "currency": currency,
    }
    for k, v in [
        ("sector", sector), ("portfolio_type", portfolio_type),
        ("asset_class", asset_class),
        ("date_of_first_investment", date_of_first_investment),
        ("notes", notes), ("primary_contact_email", primary_contact_email),
    ]:
        if v:
            payload[k] = v

    try:
        resp = httpx.post(
            f"{BACKEND_API_URL}/companies",
            json=payload, headers=_headers(), timeout=15,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code == 201:
        row = resp.json()
        return json.dumps({
            "status": "success",
            "message": f"Company '{row.get('display_name', company_name)}' created. "
                       f"ID: {row['id']}.",
            "company_id": row["id"],
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 7: manage_reminder_schedule ─────────────────────────────────────────

def manage_reminder_schedule(
    company_name: str,
    action: str,
    reminder_type: str = "MIS_MONTHLY",
    cadence_days: int = 7,
    first_reminder_offset_days: int = 5,
    escalation_threshold: int = 3,
    dry_run: bool = True,
) -> str:
    """
    Create, update, or disable a MIS reminder schedule for a company.

    Use dry_run=True to preview, then dry_run=False to execute.

    Args:
        company_name: Company name (partial match).
        action: 'create', 'update', 'disable', or 'enable'.
        reminder_type: 'MIS_MONTHLY','MIS_QUARTERLY','VALUATION_REVIEW','CUSTOM'.
        cadence_days: Days between reminders. Default 7.
        first_reminder_offset_days: Days before deadline to send first reminder.
        escalation_threshold: Unanswered reminders before escalation.
        dry_run: True = preview. False = execute.
    """
    VALID_ACTIONS = {"create", "update", "disable", "enable"}
    if action not in VALID_ACTIONS:
        return _err(f"Invalid action '{action}'. Valid: {sorted(VALID_ACTIONS)}")

    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    # For update/disable/enable we need the existing schedule ID
    existing: dict | None = None
    if action != "create":
        try:
            sr = httpx.get(
                f"{BACKEND_API_URL}/reminders/schedules",
                params={"company_id": company["id"]},
                headers=_headers(), timeout=10,
            )
            if sr.status_code == 200:
                schedules = sr.json()
                existing = next(
                    (s for s in schedules if s["reminder_type"] == reminder_type), None
                )
        except Exception as exc:
            return _err(f"Could not fetch schedules: {exc}")

        if not existing:
            return _err(
                f"No {reminder_type} schedule found for {company['display_name']}. "
                "Use action='create' to create one."
            )

    if action == "create":
        summary = (
            f"Create {reminder_type} reminder schedule for {company['display_name']}: "
            f"every {cadence_days} days, first reminder {first_reminder_offset_days}d "
            f"before deadline, escalate after {escalation_threshold} reminders"
        )
    elif action == "disable":
        summary = f"Disable {reminder_type} reminders for {company['display_name']}"
    elif action == "enable":
        summary = f"Re-enable {reminder_type} reminders for {company['display_name']}"
    else:
        summary = (
            f"Update {reminder_type} reminder schedule for {company['display_name']}: "
            f"cadence → {cadence_days} days"
        )

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({"status": "pending_confirmation", "summary": summary})

    try:
        if action == "create":
            resp = httpx.post(
                f"{BACKEND_API_URL}/reminders/schedules",
                json={
                    "company_id": company["id"],
                    "reminder_type": reminder_type,
                    "cadence_days": cadence_days,
                    "enabled": True,
                    "first_reminder_offset_days": first_reminder_offset_days,
                    "escalation_threshold": escalation_threshold,
                },
                headers=_headers(), timeout=10,
            )
            ok = resp.status_code == 201
        else:
            patch_body: dict = {}
            if action == "disable":
                patch_body = {"enabled": False}
            elif action == "enable":
                patch_body = {"enabled": True}
            else:
                patch_body = {
                    "cadence_days": cadence_days,
                    "first_reminder_offset_days": first_reminder_offset_days,
                    "escalation_threshold": escalation_threshold,
                }
            resp = httpx.patch(
                f"{BACKEND_API_URL}/reminders/schedules/{existing['id']}",
                json=patch_body, headers=_headers(), timeout=10,
            )
            ok = resp.status_code == 200
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if ok:
        return json.dumps({
            "status": "success",
            "message": f"Reminder schedule {action}d for {company['display_name']}.",
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 8: correct_transaction ───────────────────────────────────────────────

def correct_transaction(
    company_name: str,
    action: str = "update",
    transaction_id: int = None,
    transaction_date: str = None,
    transaction_type: str = None,
    new_amount_cr: float = None,
    new_date: str = None,
    new_notes: str = None,
    dry_run: bool = True,
) -> str:
    """
    Correct an existing transaction — update a field or delete it entirely.

    Locate the transaction by transaction_id (most precise), or by
    company + transaction_date + transaction_type combination.

    WARNING: Deleting a transaction is permanent and cannot be undone.
    Updating amount_cr triggers a MOIC recomputation.

    Use dry_run=True to preview, then dry_run=False to execute.

    Args:
        company_name: Company name (partial match).
        action: 'update' or 'delete'.
        transaction_id: Exact DB ID (preferred — most precise).
        transaction_date: ISO date to locate the transaction if ID not known.
        transaction_type: Narrows the lookup when using date-based search.
        new_amount_cr: Updated amount for 'update' action.
        new_date: Updated transaction date for 'update' action.
        new_notes: Updated notes for 'update' action.
        dry_run: True = preview. False = execute.
    """
    if action not in ("update", "delete"):
        return _err("action must be 'update' or 'delete'.")

    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    # Fetch all transactions and locate the target
    try:
        tr = httpx.get(
            f"{BACKEND_API_URL}/companies/{company['id']}/transactions",
            headers=_headers(), timeout=10,
        )
    except Exception as exc:
        return _err(f"Could not fetch transactions: {exc}")

    if tr.status_code != 200:
        return _err(f"Could not fetch transactions: {tr.status_code}")

    all_txns = tr.json()
    txn: dict | None = None

    if transaction_id:
        txn = next((t for t in all_txns if t["id"] == transaction_id), None)
    elif transaction_date:
        matches = [t for t in all_txns if t["transaction_date"] == transaction_date]
        if transaction_type:
            matches = [t for t in matches if t["transaction_type"] == transaction_type]
        if len(matches) == 1:
            txn = matches[0]
        elif len(matches) > 1:
            return _err(
                f"Multiple transactions found on {transaction_date} for "
                f"{company['display_name']}. Provide transaction_id to be precise. "
                f"IDs found: {[t['id'] for t in matches]}"
            )

    if not txn:
        return _err(
            "Transaction not found. Provide transaction_id or "
            "company_name + transaction_date (+ transaction_type to narrow)."
        )

    if action == "delete":
        summary = (
            f"⚠ PERMANENTLY DELETE transaction ID {txn['id']}: "
            f"{txn['transaction_type']} of ₹{abs(float(txn['amount_cr'])):.2f} Cr "
            f"for {company['display_name']} on {txn['transaction_date']}. "
            f"THIS CANNOT BE UNDONE."
        )
        dry_run = _voice_dry_run(dry_run)
        if dry_run:
            return json.dumps({
                "status": "pending_confirmation",
                "summary": summary,
                "warning": "Permanent deletion. MOIC will be recomputed after deletion.",
            })
        try:
            resp = httpx.delete(
                f"{BACKEND_API_URL}/transactions/{txn['id']}",
                headers=_headers(), timeout=15,
            )
        except Exception as exc:
            return _err(f"Could not reach backend: {exc}")

        if resp.status_code == 204:
            return json.dumps({
                "status": "success",
                "message": f"Transaction ID {txn['id']} deleted. MOIC has been recomputed.",
            })
        return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")

    # action == "update"
    updates: dict = {}
    changes: list[str] = []

    if new_amount_cr is not None:
        updates["amount"] = abs(new_amount_cr)   # TransactionUpdate uses `amount` (non-negative)
        changes.append(
            f"amount ₹{abs(float(txn['amount_cr'])):.2f} Cr "
            f"→ ₹{abs(new_amount_cr):.2f} Cr"
        )
    if new_date:
        updates["transaction_date"] = new_date
        changes.append(f"date {txn['transaction_date']} → {new_date}")
    if new_notes:
        updates["notes"] = new_notes
        changes.append("notes updated")

    if not updates:
        return _err("No fields to update. Provide new_amount_cr, new_date, or new_notes.")

    summary = (
        f"Update transaction ID {txn['id']} for {company['display_name']}: "
        f"{'; '.join(changes)}"
    )
    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({"status": "pending_confirmation", "summary": summary})

    try:
        resp = httpx.patch(
            f"{BACKEND_API_URL}/transactions/{txn['id']}",
            json=updates, headers=_headers(), timeout=15,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code == 200:
        return json.dumps({
            "status": "success",
            "message": f"Transaction ID {txn['id']} updated. {'; '.join(changes)}. "
                       "MOIC has been recomputed.",
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")


# ── Tool 9: correct_mis_metric ────────────────────────────────────────────────

# Allowed columns per MIS table — prevents arbitrary column injection
_MIS_MONTHLY_COLS = frozenset({
    "revenue_lacs", "total_income_lacs", "indirect_income_lacs",
    "cogs_lacs", "gross_margin_lacs", "gross_margin_pct",
    "total_operating_costs_lacs", "manpower_cost_lacs", "rent_lacs",
    "marketing_lacs", "ebitda_lacs", "ebitda_pct",
})
_MIS_BU_COLS = frozenset({
    "revenue_lacs", "cogs_lacs", "gross_margin_lacs", "gross_margin_pct",
    "operating_costs_lacs", "ebitda_lacs", "ebitda_pct",
    "channel_dine_in_lacs", "channel_aggregator_a_lacs",
    "channel_aggregator_b_lacs", "channel_aggregator_d_lacs",
    "channel_catering_lacs", "channel_franchise_lacs",
})


def correct_mis_metric(
    company_id: str,
    month: str,
    metric: str,
    new_value: float,
    geography: str = "consolidated",
    bu_id: str = None,
    dry_run: bool = True,
) -> str:
    """
    Correct a single MIS financial metric for a specific company and month.

    Targets mis_monthly (company-level) by default.
    When bu_id is provided, targets mis_bu_monthly instead.

    Uses direct psycopg2 — the MIS router has no row-level PATCH endpoint.
    A timestamped audit note is appended to voice_call_logs automatically.

    Use dry_run=True to preview current value vs proposed.

    Args:
        company_id: 'company_01' or 'company_02'.
        month: 'YYYY-MM' (e.g. '2025-04').
        metric: Column name to correct. See allowed lists in the plan.
        new_value: Corrected value. Monetary columns in INR Lacs.
                   Percentage columns as DECIMAL (0.12 = 12%, NOT 12).
        geography: 'consolidated', 'country_a', or 'city_z'.
                   Ignored when bu_id is provided.
        bu_id: BU identifier e.g. 'BU_03'. When set, targets mis_bu_monthly.
        dry_run: True = preview with current value. False = execute.
    """
    company_id = company_id.lower().strip()
    if company_id not in ("company_01", "company_02"):
        return _err("company_id must be 'company_01' or 'company_02'.")

    try:
        year, mon = month.split("-")
        month_date = f"{int(year)}-{int(mon):02d}-01"
    except (ValueError, AttributeError):
        return _err("month must be YYYY-MM format (e.g. '2025-04').")

    use_bu = bu_id is not None
    table  = "mis_bu_monthly" if use_bu else "mis_monthly"
    allowed = _MIS_BU_COLS if use_bu else _MIS_MONTHLY_COLS

    if metric not in allowed:
        return _err(
            f"'{metric}' is not a correctable column in {table}. "
            f"Allowed: {sorted(allowed)}"
        )

    # Read current value
    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            if use_bu:
                cur.execute(
                    f"SELECT {metric} FROM mis_bu_monthly "
                    "WHERE company_id = %s AND bu_id = %s AND month_date = %s",
                    (company_id, bu_id, month_date),
                )
            else:
                cur.execute(
                    f"SELECT {metric} FROM mis_monthly "
                    "WHERE company_id = %s AND geography = %s AND month_date = %s",
                    (company_id, geography, month_date),
                )
            row = cur.fetchone()
    except Exception as exc:
        return _err(f"DB read failed: {exc}")

    if not row:
        target = f"{company_id}/{bu_id}" if use_bu else f"{company_id}/{geography}"
        return _err(
            f"No MIS record found for {target} in {month}. "
            "Check company_id, month, and geography/bu_id."
        )

    current_value = float(row[metric]) if row[metric] is not None else None
    label = f"{company_id}" + (f"/{bu_id}" if use_bu else f"/{geography}")

    summary = (
        f"Update {metric} for {label} in {month}: "
        f"{current_value} → {new_value} (in {table})"
    )

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({
            "status": "pending_confirmation",
            "summary": summary,
            "table": table,
            "company_id": company_id,
            "month": month,
            "metric": metric,
            "current_value": current_value,
            "proposed_value": new_value,
        })

    try:
        with get_conn() as conn, get_cursor(conn) as cur:
            if use_bu:
                cur.execute(
                    f"UPDATE mis_bu_monthly SET {metric} = %s "
                    "WHERE company_id = %s AND bu_id = %s AND month_date = %s",
                    (new_value, company_id, bu_id, month_date),
                )
            else:
                cur.execute(
                    f"UPDATE mis_monthly SET {metric} = %s "
                    "WHERE company_id = %s AND geography = %s AND month_date = %s",
                    (new_value, company_id, geography, month_date),
                )
            affected = cur.rowcount
            conn.commit()
    except Exception as exc:
        return _err(f"DB write failed: {exc}")

    if affected == 0:
        return _err("Update matched 0 rows — record may have changed. Verify and retry.")

    audit = (
        f"[Chatbot correction {datetime.utcnow().strftime('%Y-%m-%dT%H:%M')}Z] "
        f"{metric}: {current_value} → {new_value}"
    )
    return json.dumps({
        "status": "success",
        "message": f"{metric} for {label} in {month} updated: {current_value} → {new_value}.",
        "audit_note": audit,
    })


# ── Tool: get_reminder_logs ──────────────────────────────────────────────────

def get_reminder_logs(
    company_name: str,
    limit: int = 10,
) -> str:
    """
    Retrieve the most recent MIS reminder log entries for a portfolio company.

    Use this to answer questions like:
      "When was the last reminder sent to Company_01?"
      "Has a reminder gone out this month for Company_02?"
      "How many reminders have we sent and were any escalations?"

    Shows: sent timestamp, recipient email, escalation flag, status, and the
    reporting period the reminder related to.

    Args:
        company_name: Company name (partial match).
        limit: Number of recent log entries to return (default 10, max 50).
    """
    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    limit = max(1, min(limit, 50))

    try:
        resp = httpx.get(
            f"{BACKEND_API_URL}/reminders/logs",
            params={"company_id": company["id"], "limit": limit, "offset": 0},
            headers=_headers(),
            timeout=10,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code != 200:
        return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    items = data.get("items", [])

    if not items:
        return json.dumps({
            "company": company["display_name"],
            "message": f"No reminder logs found for {company['display_name']}. "
                       "No reminders have been sent yet.",
            "total": 0,
        })

    return json.dumps({
        "company": company["display_name"],
        "total_on_record": data.get("total", len(items)),
        "showing": len(items),
        "logs": [
            {
                "sent_at": log["sent_at"],
                "recipient_email": log["recipient_email"],
                "subject": log["subject"],
                "is_escalation": log["is_escalation"],
                "status": log["status"],
                "related_period": log["related_period"],
            }
            for log in items
        ],
    })


# ── Tool 10: deactivate_company ───────────────────────────────────────────────

def deactivate_company(
    company_name: str,
    dry_run: bool = True,
) -> str:
    """
    Soft-delete (deactivate) a portfolio company.

    Sets is_active = False. The company disappears from all active portfolio
    views and chatbot queries. All historical data (transactions, valuations,
    MIS) is preserved and remains queryable.

    This is REVERSIBLE: an admin can restore it via update_company or the UI.

    Use dry_run=True to preview. The summary shows the full position
    (invested, current value, MOIC, transaction count) before you confirm.

    Args:
        company_name: Company name (partial match).
        dry_run: True = show full position summary. False = execute soft-delete.
    """
    company = _resolve_company(company_name)
    if not company:
        return _err(f"Company not found: '{company_name}'")

    if not company.get("is_active", True):
        return _err(f"{company['display_name']} is already inactive. Nothing to do.")

    # Fetch transaction count for the dry_run summary
    txn_count: int | None = None
    try:
        tr = httpx.get(
            f"{BACKEND_API_URL}/companies/{company['id']}/transactions",
            headers=_headers(), timeout=10,
        )
        if tr.status_code == 200:
            txn_count = len(tr.json())
    except Exception:
        pass

    inv_cr = company.get("investment_value_cr")
    cur_cr = company.get("current_value_cr")
    moic   = company.get("moic")

    lines = [f"Deactivate (soft-delete): {company['display_name']}"]
    lines.append(
        f"  Sector: {company.get('sector','N/A')} | "
        f"Status: {company.get('investment_status','N/A')} | "
        f"Type: {company.get('portfolio_type','N/A')}"
    )
    if inv_cr is not None:
        lines.append(
            f"  Invested: ₹{abs(float(inv_cr)):.2f} Cr | "
            f"Current: ₹{float(cur_cr or 0):.2f} Cr | "
            f"MOIC: {float(moic or 0):.2f}x"
        )
    if txn_count is not None:
        lines.append(f"  Transactions on record: {txn_count}")
    lines.append(
        "  The company will be hidden from all active portfolio views. "
        "All data is preserved and can be restored via the UI or update_company."
    )
    summary = "\n".join(lines)

    dry_run = _voice_dry_run(dry_run)
    if dry_run:
        return json.dumps({
            "status": "pending_confirmation",
            "summary": summary,
            "company": company["display_name"],
            "company_id": company["id"],
            "invested_cr": abs(float(inv_cr)) if inv_cr else None,
            "current_value_cr": float(cur_cr) if cur_cr else None,
            "transaction_count": txn_count,
            "reversible": True,
        })

    try:
        resp = httpx.delete(
            f"{BACKEND_API_URL}/companies/{company['id']}",
            headers=_headers(), timeout=15,
        )
    except Exception as exc:
        return _err(f"Could not reach backend: {exc}")

    if resp.status_code == 204:
        return json.dumps({
            "status": "success",
            "message": (
                f"{company['display_name']} has been deactivated and removed "
                "from active portfolio views. All historical data is preserved."
            ),
        })
    return _err(f"Backend returned {resp.status_code}: {resp.text[:300]}")
