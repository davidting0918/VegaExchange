"""
Pool domain models — AMM pool types, symbol parsing, request models.
"""

import re
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.enums import OrderSide


PeriodKind = Literal["1H", "1D", "1W", "1M", "1Y", "ALL"]


def parse_symbol_path(symbol_path: str) -> str:
    """
    Parse symbol path and build full symbol string.

    Input format: {BASE}-{QUOTE}-{SETTLE}-{MARKET}
    Output format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
    """
    parts = symbol_path.upper().split("-")
    if len(parts) != 4:
        return symbol_path.upper()
    base, quote, settle, market = parts
    return f"{base}/{quote}-{settle}:{market}"


def parse_symbol_path_components(symbol_path: str) -> tuple[str, str, str, str] | None:
    """Parse symbol path and return (base, quote, settle, market) components."""
    parts = symbol_path.upper().split("-")
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def parse_symbol_string(symbol_str: str) -> tuple[str, str, str, str] | None:
    """Parse symbol string and return (base, quote, settle, market) components."""
    match = re.match(r"^([^/]+)/([^-]+)-([^:]+):(.+)$", symbol_str.upper())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3), match.group(4)


class SwapRequest(BaseModel):
    """AMM swap request"""

    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Buy or sell base asset")
    amount_in: Decimal = Field(..., gt=0, description="Amount to swap in")
    min_amount_out: Optional[Decimal] = Field(None, description="Minimum amount to receive (slippage protection)")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()


class AddLiquidityRequest(BaseModel):
    """Request to add liquidity to AMM pool"""

    symbol: str = Field(..., description="Trading pair symbol")
    base_amount: Decimal = Field(..., gt=0, description="Amount of base asset to add")
    quote_amount: Decimal = Field(..., gt=0, description="Amount of quote asset to add")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()


class RemoveLiquidityRequest(BaseModel):
    """Request to remove liquidity from AMM pool"""

    symbol: str = Field(..., description="Trading pair symbol")
    lp_shares: Decimal = Field(..., gt=0, description="Amount of LP shares to burn")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()
