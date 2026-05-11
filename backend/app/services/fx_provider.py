"""
Thin HTTP client for the live FX provider.

Pure: no DB, no Celery, no settings beyond what's passed in. Keeps the loader
task and the tests trivially mockable, and isolates provider-specific quirks
here:

- currencylayer free tier: source locked to USD, params use `currencies=`,
  response keys quotes as concatenated pairs like `USDINR` under `quotes`.
- fixer free tier:        base locked to EUR (no `base`/`source` param),
                           params use `symbols=`, response is flat
                           `{currency: rate}` under `rates`.
"""
from __future__ import annotations

from decimal import Decimal

import httpx

_CURRENCYLAYER_URL = "https://api.currencylayer.com/live"
_FIXER_URL = "https://data.fixer.io/api/latest"


class FxProviderError(RuntimeError):
    """Raised when the upstream provider returns a non-success payload."""


def fetch_base_quotes(
    *,
    api_key: str,
    base_currency: str,
    currencies: list[str],
    provider: str = "currencylayer",
    timeout_sec: int = 15,
) -> dict[str, Decimal]:
    """
    Return `{currency: base→currency rate}` for each requested currency.

    Always includes the base itself (rate 1) so callers can triangulate without
    a special case. Raises FxProviderError on a non-success payload.
    """
    base = base_currency.upper()
    wanted = sorted({c.upper() for c in currencies if c and c.upper() != base})

    if not wanted:
        return {base: Decimal("1")}

    url, params, response_key, key_prefix = _build_request(provider, api_key, base, wanted)

    resp = httpx.get(url, params=params, timeout=timeout_sec)
    # Read JSON first — providers often return 200 OK with {"success": false, ...},
    # and we want the structured error code surfaced, not buried by raise_for_status.
    try:
        payload = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise FxProviderError(f"FX provider returned non-JSON body: {resp.text[:200]!r}")

    if not payload.get("success", False):
        err = payload.get("error", {})
        raise FxProviderError(f"FX provider error: {err}")

    resp.raise_for_status()

    raw = payload.get(response_key)
    if not isinstance(raw, dict):
        raise FxProviderError(f"FX provider returned no '{response_key}': {payload!r}")

    quotes: dict[str, Decimal] = {base: Decimal("1")}
    for ccy in wanted:
        key = f"{key_prefix}{ccy}" if key_prefix else ccy
        if key not in raw:
            continue
        quotes[ccy] = Decimal(str(raw[key]))
    return quotes


def _build_request(
    provider: str, api_key: str, base: str, wanted: list[str]
) -> tuple[str, dict[str, str], str, str]:
    """Per-provider request shape. Returns (url, params, response_key, key_prefix)."""
    if provider == "currencylayer":
        return (
            _CURRENCYLAYER_URL,
            {
                "access_key": api_key,
                "currencies": ",".join(wanted),
                "source": base,
            },
            "quotes",
            base,  # currencylayer keys are "USDINR" etc.
        )
    if provider == "fixer":
        # Free tier locks base to EUR and rejects any `base=`/`source=` param.
        return (
            _FIXER_URL,
            {
                "access_key": api_key,
                "symbols": ",".join(wanted),
            },
            "rates",
            "",  # fixer returns flat {currency: rate}
        )
    raise FxProviderError(f"Unsupported FX provider: {provider}")
