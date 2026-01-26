"""
Enum definitions for VegaExchange

Using IntEnum for database storage efficiency.
Integer values are stored in database, providing faster comparisons and smaller indexes.
"""

from enum import IntEnum


class EngineType(IntEnum):
    """
    Trading engine types
    Database: SMALLINT
    """
    AMM = 0
    CLOB = 1


class SymbolStatus(IntEnum):
    """
    Symbol trading status
    Database: SMALLINT
    """
    ACTIVE = 0
    PAUSED = 1
    MAINTENANCE = 2


class OrderSide(IntEnum):
    """
    Order side (buy/sell)
    Database: SMALLINT
    """
    BUY = 0
    SELL = 1


class OrderType(IntEnum):
    """
    Order type
    Database: SMALLINT
    """
    MARKET = 0
    LIMIT = 1


class OrderStatus(IntEnum):
    """
    Order status
    Database: SMALLINT
    """
    OPEN = 0
    PARTIAL = 1
    FILLED = 2
    CANCELLED = 3


class TradeStatus(IntEnum):
    """
    Trade execution status
    Database: SMALLINT
    """
    PENDING = 0
    COMPLETED = 1
    FAILED = 2
