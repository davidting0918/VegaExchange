"""
Response models for VegaExchange API

NOTE: Domain-specific models are being migrated to backend/models/<domain>.py.
- User models → backend/models/user.py
- Auth models → backend/models/auth.py
- Common models (APIResponse) → backend/models/common.py
This file retains models not yet migrated to domain files.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType, TradeStatus

# Re-export migrated models for backward compatibility
from backend.models.common import APIResponse, PaginatedResponse  # noqa: F401
from backend.models.user import UserResponse, BalanceResponse  # noqa: F401


class SymbolConfigResponse(BaseModel):
    """Symbol configuration response"""

    symbol_id: int
    symbol: str
    base: str
    quote: str
    engine_type: EngineType
    is_active: bool
    engine_params: Dict[str, Any]
    min_trade_amount: Decimal
    max_trade_amount: Decimal
    price_precision: int
    quantity_precision: int
    created_at: datetime


class AMMPoolResponse(BaseModel):
    """AMM pool information"""

    pool_id: str
    symbol: str
    reserve_base: Decimal
    reserve_quote: Decimal
    current_price: Decimal = Field(description="reserve_quote / reserve_base")
    k_value: Decimal
    fee_rate: Decimal
    total_lp_shares: Decimal
    total_volume_base: Decimal
    total_volume_quote: Decimal
    total_fees_collected: Decimal


class OrderResponse(BaseModel):
    """Order information response"""

    order_id: str
    symbol: str
    user_id: str
    side: OrderSide
    order_type: OrderType
    price: Optional[Decimal]
    quantity: Decimal
    filled_quantity: Decimal
    remaining_quantity: Decimal
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


class OrderBookLevel(BaseModel):
    """Single price level in order book"""

    price: Decimal
    quantity: Decimal
    order_count: int


class OrderBookResponse(BaseModel):
    """Order book snapshot"""

    symbol: str
    bids: List[OrderBookLevel] = Field(description="Buy orders, sorted by price desc")
    asks: List[OrderBookLevel] = Field(description="Sell orders, sorted by price asc")
    timestamp: datetime


class TradeResponse(BaseModel):
    """Trade execution response"""

    trade_id: str
    symbol: str
    user_id: str
    side: OrderSide
    engine_type: EngineType
    price: Decimal
    quantity: Decimal
    quote_amount: Decimal
    fee_amount: Decimal
    fee_asset: str
    status: TradeStatus
    engine_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class MarketDataResponse(BaseModel):
    """Market data for a symbol"""

    symbol: str
    engine_type: EngineType
    current_price: Decimal
    price_24h_ago: Optional[Decimal] = None
    price_change_24h: Optional[Decimal] = None
    price_change_pct_24h: Optional[Decimal] = None
    volume_24h_base: Decimal = Decimal("0")
    volume_24h_quote: Decimal = Decimal("0")
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None

    # AMM-specific
    reserve_base: Optional[Decimal] = None
    reserve_quote: Optional[Decimal] = None

    # CLOB-specific
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    spread: Optional[Decimal] = None

    timestamp: datetime


class QuoteResponse(BaseModel):
    """Quote for a potential trade (preview without execution)"""

    symbol: str
    side: OrderSide
    engine_type: EngineType
    input_amount: Decimal
    input_asset: str
    output_amount: Decimal
    output_asset: str
    effective_price: Decimal
    price_impact: Optional[Decimal] = Field(None, description="Price impact percentage for AMM")
    fee_amount: Decimal
    fee_asset: str

    # AMM-specific
    slippage: Optional[Decimal] = None

    # CLOB-specific
    fills: Optional[List[Dict[str, Any]]] = Field(None, description="Simulated order fills")



# APIResponse and PaginatedResponse have been moved to backend/models/common.py
# They are re-exported above for backward compatibility.
