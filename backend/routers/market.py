"""
Market Data API Routes — thin router, delegates to services/market.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.core.dependencies import get_router
from backend.engines.engine_router import EngineRouter
from backend.models.common import APIResponse
from backend.services import market as market_service

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("", response_model=APIResponse)
async def get_all_markets(
    symbol: Optional[str] = Query(None, description="Symbol. When provided, returns market data for that symbol."),
    engine_type: Optional[int] = Query(None, description="Engine type: 0=AMM, 1=CLOB"),
    router: EngineRouter = Depends(get_router),
):
    """Get all active markets, or market data for a specific symbol."""
    data = await market_service.get_all_markets(router, symbol, engine_type)
    return APIResponse(success=True, data=data)


@router.get("/engines", response_model=APIResponse)
async def get_symbol_engines(
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    router: EngineRouter = Depends(get_router),
):
    """Get all available engines for a symbol."""
    data = await market_service.get_symbol_engines(router, symbol)
    return APIResponse(success=True, data=data)


@router.get("/klines", response_model=APIResponse)
async def get_klines(
    symbol: str = Query(..., description="Symbol (e.g. BTC/USDT-USDT:SPOT)"),
    interval: str = Query("1h", description="Candle interval: 1m, 5m, 15m, 1h, 4h, 1d"),
    engine_type: Optional[int] = Query(None, description="Engine type: 0=AMM, 1=CLOB"),
    limit: int = Query(100, ge=1, le=500, description="Number of candles to return"),
):
    """Get OHLCV kline data with forward-fill for empty intervals."""
    data = await market_service.get_klines(symbol, interval, engine_type, limit)
    return APIResponse(success=True, data=data)
