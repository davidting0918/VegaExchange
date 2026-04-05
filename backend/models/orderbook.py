"""
Orderbook domain models — CLOB order request models.
"""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.enums import OrderSide, OrderType


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
