"""
Pool domain models — AMM pool types and symbol parsing.

Request models (SwapRequest, AddLiquidityRequest, RemoveLiquidityRequest) are still
in models/requests.py and will be migrated here during cleanup (#45).
"""

import re
from typing import Literal, Optional


PeriodKind = Literal["1H", "1D", "1W", "1M", "1Y", "ALL"]


def parse_symbol_path(symbol_path: str) -> str:
    """
    Parse symbol path and build full symbol string.

    Input format: {BASE}-{QUOTE}-{SETTLE}-{MARKET}
    Output format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
    Example: AMM-USDT-USDT-SPOT -> AMM/USDT-USDT:SPOT
    """
    parts = symbol_path.upper().split("-")
    if len(parts) != 4:
        return symbol_path.upper()
    base, quote, settle, market = parts
    return f"{base}/{quote}-{settle}:{market}"


def parse_symbol_path_components(symbol_path: str) -> tuple[str, str, str, str] | None:
    """
    Parse symbol path and return (base, quote, settle, market) components.

    Input format: {BASE}-{QUOTE}-{SETTLE}-{MARKET}
    """
    parts = symbol_path.upper().split("-")
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def parse_symbol_string(symbol_str: str) -> tuple[str, str, str, str] | None:
    """
    Parse symbol string and return (base, quote, settle, market) components.

    Input format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
    """
    match = re.match(r"^([^/]+)/([^-]+)-([^:]+):(.+)$", symbol_str.upper())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3), match.group(4)
