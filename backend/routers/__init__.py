"""
API Routers for VegaExchange
"""

from backend.routers.auth import router as auth_router
from backend.routers.market import router as market_router
from backend.routers.symbols import router as symbols_router
from backend.routers.trading import router as trading_router
from backend.routers.users import router as users_router

__all__ = [
    "auth_router",
    "symbols_router",
    "trading_router",
    "market_router",
    "users_router",
]
