"""
Response models for VegaExchange API
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType, SymbolStatus, TradeStatus


class UserResponse(BaseModel):
    """User information response"""

    id: UUID
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_admin: bool = False
    created_at: datetime
    last_login_at: datetime


class BalanceResponse(BaseModel):
    """User balance for a single asset"""

    asset: str
    available: Decimal
    locked: Decimal
    total: Decimal = Field(description="available + locked")


class SymbolConfigResponse(BaseModel):
    """Symbol configuration response"""

    id: UUID
    symbol: str
    base_asset: str
    quote_asset: str
    engine_type: EngineType
    status: SymbolStatus
    engine_params: Dict[str, Any]
    min_trade_amount: Decimal
    max_trade_amount: Decimal
    price_precision: int
    quantity_precision: int
    created_at: datetime


class AMMPoolResponse(BaseModel):
    """AMM pool information"""

    id: UUID
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

    id: UUID
    symbol: str
    user_id: UUID
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

    id: UUID
    symbol: str
    user_id: UUID
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


class APIResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool = True
    data: Optional[Any] = None
    error: Optional[Dict[str, str]] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""

    success: bool = True
    data: List[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
