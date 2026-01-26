"""
API Routers for VegaExchange
"""

from backend.routers.admin import router as admin_router
from backend.routers.market import router as market_router
from backend.routers.symbols import router as symbols_router
from backend.routers.trading import router as trading_router
from backend.routers.users import router as users_router

__all__ = [
    "symbols_router",
    "trading_router",
    "market_router",
    "users_router",
    "admin_router",
]
