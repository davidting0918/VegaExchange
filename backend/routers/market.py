"""
Market Data API Routes

General market data endpoints that work across all engine types.
For engine-specific operations, use /api/pool (AMM) or /api/orderbook (CLOB).

Endpoint prefix: /api/market
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.db_manager import get_db
from backend.core.dependencies import get_router
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType
from backend.models.responses import APIResponse

# Interval name → seconds mapping for kline aggregation
KLINE_INTERVALS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("", response_model=APIResponse)
async def get_all_markets(
    symbol: Optional[str] = Query(None, description="Symbol. When provided, returns market data for that symbol."),
    engine_type: Optional[int] = Query(None, description="Engine type: 0=AMM, 1=CLOB (used when symbol is provided)"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get all active markets (both AMM and CLOB), or get market data for a symbol when symbol is provided.
    """
    if symbol:
        et = EngineType(engine_type) if engine_type is not None else None
        data = await router.get_market_data(symbol.upper(), et)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        data["timestamp"] = datetime.utcnow().isoformat()
        return APIResponse(success=True, data=data)

    symbols = await router.get_all_symbols()
    markets = []
    for symbol_config in symbols:
        engine_type_val = EngineType(symbol_config["engine_type"])
        market_data = await router.get_market_data(symbol_config["symbol"], engine_type_val)
        markets.append({
            "symbol": symbol_config["symbol"],
            "base_asset": symbol_config["base"],
            "quote_asset": symbol_config["quote"],
            "engine_type": symbol_config["engine_type"],
            "engine_name": "AMM" if engine_type_val == EngineType.AMM else "CLOB",
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


@router.get("/engines", response_model=APIResponse)
async def get_symbol_engines(
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get all available engines for a symbol. Shows which engines (AMM/CLOB) are available.
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


@router.get("/klines", response_model=APIResponse)
async def get_klines(
    symbol: str = Query(..., description="Symbol (e.g. BTC/USDT-USDT:SPOT)"),
    interval: str = Query("1h", description="Candle interval: 1m, 5m, 15m, 1h, 4h, 1d"),
    engine_type: Optional[int] = Query(None, description="Engine type: 0=AMM, 1=CLOB. If omitted, includes all."),
    limit: int = Query(100, ge=1, le=500, description="Number of candles to return"),
):
    """
    Get OHLCV (Kline/candlestick) data aggregated from trades.
    Returns candles sorted by time ascending (oldest first) for chart rendering.
    Empty intervals are forward-filled with the previous close.
    """
    if interval not in KLINE_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval '{interval}'. Valid: {', '.join(KLINE_INTERVALS.keys())}",
        )

    interval_seconds = KLINE_INTERVALS[interval]
    db = get_db()
    symbol_upper = symbol.upper()

    # Build engine_type filter
    et_filter = ""
    params: list = [symbol_upper, interval_seconds, limit]
    if engine_type is not None:
        et_filter = "AND t.engine_type = $4"
        params.append(engine_type)

    # Aggregate trades into OHLCV buckets using epoch arithmetic
    raw_candles = await db.read(
        f"""
        SELECT
            (EXTRACT(EPOCH FROM t.created_at)::bigint / $2) * $2 AS bucket,
            (array_agg(t.price ORDER BY t.created_at ASC))[1] AS open,
            MAX(t.price) AS high,
            MIN(t.price) AS low,
            (array_agg(t.price ORDER BY t.created_at DESC))[1] AS close,
            SUM(t.quantity) AS volume,
            SUM(t.quote_amount) AS quote_volume,
            COUNT(*) AS trade_count
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.symbol = $1
        AND t.status = 1
        {et_filter}
        GROUP BY bucket
        ORDER BY bucket DESC
        LIMIT $3
        """,
        *params,
    )

    if not raw_candles:
        return APIResponse(success=True, data={"symbol": symbol_upper, "interval": interval, "klines": []})

    # Reverse to time-ascending order for forward-fill
    raw_candles.reverse()

    # Build a map of bucket → candle
    candle_map = {}
    for c in raw_candles:
        candle_map[int(c["bucket"])] = c

    # Generate continuous time series with forward-fill
    first_bucket = int(raw_candles[0]["bucket"])
    last_bucket = int(raw_candles[-1]["bucket"])

    klines = []
    prev_close = raw_candles[0]["close"]

    bucket = first_bucket
    while bucket <= last_bucket:
        if bucket in candle_map:
            c = candle_map[bucket]
            klines.append({
                "time": bucket,
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
                "quote_volume": c["quote_volume"],
                "trade_count": c["trade_count"],
            })
            prev_close = c["close"]
        else:
            # Forward-fill empty interval
            klines.append({
                "time": bucket,
                "open": prev_close,
                "high": prev_close,
                "low": prev_close,
                "close": prev_close,
                "volume": 0,
                "quote_volume": 0,
                "trade_count": 0,
            })
        bucket += interval_seconds

    return APIResponse(
        success=True,
        data={
            "symbol": symbol_upper,
            "interval": interval,
            "klines": klines,
        },
    )
