"""
Enum definitions for VegaExchange
"""

from enum import Enum


class EngineType(str, Enum):
    """Trading engine types"""

    AMM = "amm"
    CLOB = "clob"


class SymbolStatus(str, Enum):
    """Symbol trading status"""

    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"


class OrderSide(str, Enum):
    """Order side (buy/sell)"""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type"""

    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(str, Enum):
    """Order status"""

    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


class TradeStatus(str, Enum):
    """Trade execution status"""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
