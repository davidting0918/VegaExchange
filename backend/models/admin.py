"""
Admin domain models — symbol/pool creation requests.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.enums import EngineType


class CreateSymbolRequest(BaseModel):
    """Request to create a new trading symbol"""

    symbol: str = Field(..., description="Trading pair symbol, e.g., 'BTC-USDT'")
    base_asset: str = Field(..., description="Base asset, e.g., 'BTC'")
    quote_asset: str = Field(..., description="Quote asset, e.g., 'USDT'")
    market: Optional[str] = Field(default="spot", description="Market type: spot, perp, option, future")
    settle: Optional[str] = Field(default=None, description="Settlement asset (defaults to quote_asset if not provided)")
    engine_type: EngineType = Field(..., description="Engine type for this symbol")
    engine_params: Dict[str, Any] = Field(default_factory=dict, description="Engine-specific parameters")
    min_trade_amount: Decimal = Field(default=Decimal("0.0001"), description="Minimum trade amount")
    max_trade_amount: Decimal = Field(default=Decimal("1000000"), description="Maximum trade amount")
    price_precision: int = Field(default=8, description="Price decimal precision")
    quantity_precision: int = Field(default=8, description="Quantity decimal precision")

    @field_validator("symbol", "base_asset", "quote_asset", "market", "settle")
    @classmethod
    def uppercase_assets(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v


class CreatePoolRequest(BaseModel):
    """Request to create a new AMM pool (auto-creates symbol)"""

    symbol: str = Field(..., description="Trading pair symbol, e.g., 'BTC-USDT'")
    base_asset: str = Field(..., description="Base asset, e.g., 'BTC'")
    quote_asset: str = Field(..., description="Quote asset, e.g., 'USDT'")
    market: Optional[str] = Field(default="spot", description="Market type: spot, perp, option, future")
    settle: Optional[str] = Field(default=None, description="Settlement asset (defaults to quote_asset if not provided)")
    initial_reserve_base: Decimal = Field(..., gt=0, description="Initial base asset reserve")
    initial_reserve_quote: Decimal = Field(..., gt=0, description="Initial quote asset reserve")
    fee_rate: Decimal = Field(default=Decimal("0.003"), ge=0, le=1, description="Trading fee rate (0.003 = 0.3%)")
    min_trade_amount: Decimal = Field(default=Decimal("0.0001"), description="Minimum trade amount")
    max_trade_amount: Decimal = Field(default=Decimal("1000000"), description="Maximum trade amount")
    price_precision: int = Field(default=8, description="Price decimal precision")
    quantity_precision: int = Field(default=8, description="Quantity decimal precision")

    @field_validator("symbol", "base_asset", "quote_asset", "market", "settle")
    @classmethod
    def uppercase_assets(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.upper()
        return v
