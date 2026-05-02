"""Normalize the spreadsheet's free-text enum values to the strings our schema expects."""

PORTFOLIO_TYPE_MAP: dict[str, str] = {
    "Entity_D Core": "Entity_D_Core",
    "Entity_D Non-Core": "Entity_D_Non_Core",
    "Entity_D LLC": "Entity_D_LLC",
    "Entity_E": "Entity_E",
    "Entity_A": "Entity_A",
    "Entity_C Orig.": "Entity_C",
    "Entity_C": "Entity_C",
    "Strategic Equity": "Strategic_Equity",
    "Real Estate Debt": "Real_Estate_Debt",
    "Real Estate": "Real_Estate_Debt",
}

INVESTMENT_STATUS_MAP: dict[str, str] = {
    "Active": "Active",
    "Exit via IPO route": "Exit_via_IPO",
    "Exit via Share swap": "Exit_via_Share_swap",
    "Matured": "Matured",
    "Written off": "Written_off",
    "Write_off": "Written_off",
}

ASSET_CLASS_MAP: dict[str, str] = {
    "Direct Equity": "Direct_Equity",
    "Fund Investment": "Fund_Investment",
    "Debt Instrument": "Debt_Instrument",
}

PORTFOLIO_STATUS_MAP: dict[str, str] = {
    "Unrealized": "Unrealized",
    "Realized": "Realized",
    "Unrealised": "Unrealized",
    "Realised": "Realized",
}


def _clean(raw: object) -> str | None:
    """Trim whitespace and treat empty / None as None."""
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def normalize_portfolio_type(raw: object) -> str | None:
    s = _clean(raw)
    if s is None:
        return None
    return PORTFOLIO_TYPE_MAP.get(s)


def normalize_investment_status(raw: object) -> str | None:
    s = _clean(raw)
    if s is None:
        return None
    return INVESTMENT_STATUS_MAP.get(s)


def normalize_asset_class(raw: object) -> str | None:
    s = _clean(raw)
    if s is None:
        return None
    return ASSET_CLASS_MAP.get(s)


def normalize_portfolio_status(raw: object) -> str | None:
    s = _clean(raw)
    if s is None:
        return None
    return PORTFOLIO_STATUS_MAP.get(s)
