"""
Market Data API Routes
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/{symbol}", response_model=APIResponse)
async def get_market_data(symbol: str, router: EngineRouter = Depends(get_router)):
    """
    Get current market data for a symbol.

    Returns engine-specific data based on the symbol's engine type.

    For AMM:
        - current_price, reserve_base, reserve_quote, fee_rate

    For CLOB:
        - current_price, best_bid, best_ask, spread, order book depth
    """
    data = await router.get_market_data(symbol.upper())

    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])

    data["timestamp"] = datetime.utcnow().isoformat()

    return APIResponse(success=True, data=data)


@router.get("/{symbol}/orderbook", response_model=APIResponse)
async def get_orderbook(
    symbol: str,
    levels: int = Query(20, ge=1, le=100, description="Number of price levels"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get order book for a CLOB symbol.

    Returns aggregated bids and asks at each price level.
    """
    engine = await router._get_engine(symbol.upper())

    if not engine:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if engine.engine_type != EngineType.CLOB:
        raise HTTPException(status_code=400, detail="Order book only available for CLOB symbols")

    # Access the order book from CLOB engine
    order_book = await engine._get_order_book(levels)

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "bids": order_book["bids"],
            "asks": order_book["asks"],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@router.get("/{symbol}/pool", response_model=APIResponse)
async def get_pool_data(symbol: str, router: EngineRouter = Depends(get_router)):
    """
    Get AMM pool data for a symbol.

    Returns reserve amounts, k value, and trading statistics.
    """
    engine = await router._get_engine(symbol.upper())

    if not engine:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if engine.engine_type != EngineType.AMM:
        raise HTTPException(status_code=400, detail="Pool data only available for AMM symbols")

    pool = await engine._get_pool()

    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool found for '{symbol}'")

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "reserve_base": float(pool["reserve_base"]),
            "reserve_quote": float(pool["reserve_quote"]),
            "k_value": float(pool["k_value"]),
            "fee_rate": float(pool["fee_rate"]),
            "total_volume_base": float(pool["total_volume_base"]),
            "total_volume_quote": float(pool["total_volume_quote"]),
            "total_fees_collected": float(pool["total_fees_collected"]),
            "total_lp_shares": float(pool["total_lp_shares"]),
            "current_price": float(pool["reserve_quote"]) / float(pool["reserve_base"])
            if float(pool["reserve_base"]) > 0
            else 0,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@router.get("/{symbol}/trades", response_model=APIResponse)
async def get_recent_trades(
    symbol: str,
    limit: int = Query(50, ge=1, le=200, description="Number of recent trades"),
):
    """
    Get recent trades for a symbol.

    Returns trades from all users, useful for trade history display.
    """
    db = get_db()

    trades = await db.read(
        """
        SELECT t.trade_id, t.side, t.price, t.quantity, t.quote_amount,
               t.engine_type, t.created_at
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.symbol = $1
        AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        symbol.upper(),
        limit,
    )

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "trades": trades,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@router.get("", response_model=APIResponse)
async def get_all_markets(router: EngineRouter = Depends(get_router)):
    """
    Get market data for all active symbols.

    Returns summary of all markets with current prices.
    """
    symbols = await router.get_all_symbols()

    markets = []
    for symbol_config in symbols:
        market_data = await router.get_market_data(symbol_config["symbol"])
        markets.append(
            {
                "symbol": symbol_config["symbol"],
                "base_asset": symbol_config["base"],
                "quote_asset": symbol_config["quote"],
                "engine_type": symbol_config["engine_type"],
                "current_price": market_data.get("current_price", 0),
            }
        )

    return APIResponse(
        success=True,
        data={
            "markets": markets,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
