"""
Admin domain models — symbol/pool creation, settings, whitelist requests.
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.enums import EngineType


class UpdateSymbolRequest(BaseModel):
    """Request to update an existing symbol configuration (mutable fields only)"""

    engine_params: Optional[Dict[str, Any]] = Field(None, description="Engine-specific parameters")
    min_trade_amount: Optional[Decimal] = Field(None, description="Minimum trade amount")
    max_trade_amount: Optional[Decimal] = Field(None, description="Maximum trade amount")
    price_precision: Optional[int] = Field(None, description="Price decimal precision")
    quantity_precision: Optional[int] = Field(None, description="Quantity decimal precision")
    fee_rate: Optional[Decimal] = Field(None, ge=0, le=1, description="AMM pool fee rate (only for AMM symbols)")


class UpdateSettingRequest(BaseModel):
    """Request to update a platform setting"""

    value: Any = Field(..., description="New setting value (JSONB)")


class AddWhitelistRequest(BaseModel):
    """Request to add an email to admin whitelist"""

    email: str = Field(..., description="Email address to whitelist")
    description: Optional[str] = Field(None, description="Optional note about this admin")


class UpdateUserBalanceRequest(BaseModel):
    """Request to adjust a user's balance (absolute value)"""

    currency: str = Field(..., description="Currency code (e.g., USDT)")
    available: Decimal = Field(..., ge=0, description="New available balance value")


class UpdateUserStatusRequest(BaseModel):
    """Request to enable/disable a user account"""

    is_active: bool = Field(..., description="Whether the user account should be active")


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
    init_price: Optional[Decimal] = Field(None, gt=0, description="Initial reference price for CLOB kline chart (optional)")

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
