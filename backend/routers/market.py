"""
Market Data API Routes

General market data endpoints that work across all engine types.
For engine-specific operations, use /api/pool (AMM) or /api/orderbook (CLOB).

Endpoint prefix: /api/market
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.dependencies import get_router
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("", response_model=APIResponse)
async def get_all_markets(router: EngineRouter = Depends(get_router)):
    """
    Get all active markets (both AMM and CLOB).
    
    Returns summary of all markets with current prices.
    """
    symbols = await router.get_all_symbols()
    
    markets = []
    for symbol_config in symbols:
        engine_type = EngineType(symbol_config["engine_type"])
        market_data = await router.get_market_data(symbol_config["symbol"], engine_type)
        markets.append({
            "symbol": symbol_config["symbol"],
            "base_asset": symbol_config["base"],
            "quote_asset": symbol_config["quote"],
            "engine_type": symbol_config["engine_type"],
            "engine_name": "AMM" if engine_type == EngineType.AMM else "CLOB",
            "current_price": market_data.get("current_price", 0),
        })
    
    return APIResponse(
        success=True,
        data={
            "markets": markets,
            "count": len(markets),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@router.get("/list_symbols", response_model=APIResponse)
async def list_symbols(router: EngineRouter = Depends(get_router)):
    """
    Get all active trading symbols.
    
    Same symbol may appear multiple times with different engine types.
    """
    symbols = await router.get_all_symbols()
    return APIResponse(success=True, data=symbols)


@router.get("/{symbol}", response_model=APIResponse)
async def get_market_data(
    symbol: str,
    engine_type: Optional[int] = Query(None, description="Engine type: 0=AMM, 1=CLOB"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get market data for a symbol.
    
    If symbol exists on both AMM and CLOB, use engine_type to specify.
    Otherwise returns the first available engine's data.
    """
    et = EngineType(engine_type) if engine_type is not None else None
    data = await router.get_market_data(symbol.upper(), et)
    
    if "error" in data:
        raise HTTPException(status_code=404, detail=data["error"])
    
    data["timestamp"] = datetime.utcnow().isoformat()
    
    return APIResponse(success=True, data=data)


@router.get("/{symbol}/engines", response_model=APIResponse)
async def get_symbol_engines(symbol: str, router: EngineRouter = Depends(get_router)):
    """
    Get all available engines for a symbol.
    
    Shows which engines (AMM/CLOB) are available for this symbol.
    """
    engines = await router.get_symbol_engines(symbol.upper())
    
    if not engines:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "engines": [
                {
                    "engine_type": e["engine_type"],
                    "engine_name": "AMM" if e["engine_type"] == 0 else "CLOB",
                    "market_data": e.get("market_data", {}),
                }
                for e in engines
            ],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
