"""
API Routers for VegaExchange

Router Structure:
- /api/auth      - Authentication (login, register, tokens)
- /api/user      - User profile, balances, trade history
- /api/market    - General market data (all engines)
- /api/pool      - AMM pool operations (swap, liquidity)
- /api/orderbook - CLOB orderbook operations (orders)
- /api/admin     - Admin operations (create symbols, pools)
"""

from backend.routers.admin import router as admin_router
from backend.routers.auth import router as auth_router
from backend.routers.market import router as market_router
from backend.routers.orderbook import router as orderbook_router
from backend.routers.pool import router as pool_router
from backend.routers.users import router as users_router

__all__ = [
    "admin_router",
    "auth_router",
    "market_router",
    "orderbook_router",
    "pool_router",
    "users_router",
]
