"""
Request models for VegaExchange API
"""

from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, EmailStr

from backend.models.enums import EngineType, OrderSide, OrderType


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


class TradeRequest(BaseModel):
    """Unified trade request - works for all engine types"""

    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Buy or sell")
    quantity: Optional[Decimal] = Field(None, description="Amount of base asset (for AMM buy, CLOB)")
    quote_amount: Optional[Decimal] = Field(None, description="Amount of quote asset (for AMM sell)")

    # CLOB-specific fields
    order_type: Optional[OrderType] = Field(None, description="Order type (for CLOB)")
    price: Optional[Decimal] = Field(None, description="Limit price (for CLOB limit orders)")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()

    @field_validator("quantity", "quote_amount", "price")
    @classmethod
    def validate_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Amount must be positive")
        return v


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


class PlaceOrderRequest(BaseModel):
    """CLOB order placement request"""

    symbol: str = Field(..., description="Trading pair symbol")
    side: OrderSide = Field(..., description="Buy or sell")
    order_type: OrderType = Field(..., description="Market or limit order")
    quantity: Decimal = Field(..., gt=0, description="Amount of base asset")
    price: Optional[Decimal] = Field(None, description="Limit price (required for limit orders)")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Optional[Decimal], info) -> Optional[Decimal]:
        if v is not None and v <= 0:
            raise ValueError("Price must be positive")
        return v


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


class EmailRegisterRequest(BaseModel):
    """Request to register a new user with email/password"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=3, description="Password (minimum 3 characters)")
    user_name: Optional[str] = Field(None, description="Display name (optional, defaults to email username)")


class EmailLoginRequest(BaseModel):
    """Request to login with email/password"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")
