"""
Market domain service — symbol listing, market data, kline generation.
"""

from datetime import datetime
from typing import Optional

from fastapi import HTTPException

from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType
from backend.models.market import KLINE_INTERVALS


async def get_all_markets(router: EngineRouter, symbol: Optional[str] = None, engine_type: Optional[int] = None) -> dict:
    """Get all active markets or single market data."""
    if symbol:
        et = EngineType(engine_type) if engine_type is not None else None
        data = await router.get_market_data(symbol.upper(), et)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        data["timestamp"] = datetime.utcnow().isoformat()
        return data

    symbols = await router.get_all_symbols()
    markets = []
    for sc in symbols:
        et_val = EngineType(sc["engine_type"])
        md = await router.get_market_data(sc["symbol"], et_val)
        markets.append({
            "symbol": sc["symbol"],
            "base_asset": sc["base"],
            "quote_asset": sc["quote"],
            "engine_type": sc["engine_type"],
            "engine_name": "AMM" if et_val == EngineType.AMM else "CLOB",
            "current_price": md.get("current_price", 0),
        })
    return {
        "markets": markets,
        "count": len(markets),
        "timestamp": datetime.utcnow().isoformat(),
    }


async def get_symbols(
    engine_type: Optional[int] = None,
    is_active: Optional[bool] = True,
    market: Optional[str] = None,
) -> list:
    """
    Get symbols with full config, optionally filtered.
    Includes pool info for AMM symbols via LEFT JOIN.
    Used by both exchange (is_active=True) and admin (is_active=None for all).
    """
    db = get_db()

    conditions = []
    params: list = []
    param_idx = 1

    if engine_type is not None:
        conditions.append(f"sc.engine_type = ${param_idx}")
        params.append(engine_type)
        param_idx += 1

    if is_active is not None:
        conditions.append(f"sc.is_active = ${param_idx}")
        params.append(is_active)
        param_idx += 1

    if market:
        conditions.append(f"sc.market = ${param_idx}")
        params.append(market.upper())
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    return await db.read(
        f"""
        SELECT sc.*,
               ap.pool_id, ap.reserve_base, ap.reserve_quote, ap.fee_rate,
               ap.total_lp_shares, ap.total_volume_quote, ap.total_fees_collected,
               CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE NULL END as current_price,
               CASE WHEN ap.reserve_quote IS NOT NULL THEN ap.reserve_quote * 2 ELSE NULL END as tvl_usdt
        FROM symbol_configs sc
        LEFT JOIN amm_pools ap ON sc.symbol_id = ap.symbol_id
        WHERE {where_clause}
        ORDER BY sc.created_at DESC
        """,
        *params,
    )


async def get_symbol_by_id(symbol_id: int) -> dict:
    """Get detailed symbol config + associated pool data by symbol_id."""
    db = get_db()

    symbol = await db.read_one(
        """
        SELECT sc.*,
               ap.pool_id, ap.reserve_base, ap.reserve_quote, ap.k_value,
               ap.fee_rate, ap.total_lp_shares, ap.total_volume_base, ap.total_volume_quote,
               ap.total_fees_collected, ap.is_active as pool_is_active,
               CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE NULL END as current_price,
               CASE WHEN ap.reserve_quote IS NOT NULL THEN ap.reserve_quote * 2 ELSE NULL END as tvl_usdt
        FROM symbol_configs sc
        LEFT JOIN amm_pools ap ON sc.symbol_id = ap.symbol_id
        WHERE sc.symbol_id = $1
        """,
        symbol_id,
    )

    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol with id {symbol_id} not found")

    return symbol


async def get_symbol_engines(router: EngineRouter, symbol: str) -> dict:
    """Get available engines for a symbol."""
    engines = await router.get_symbol_engines(symbol.upper())
    if not engines:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    return {
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
    }


async def get_klines(
    symbol: str,
    interval: str,
    engine_type: Optional[int] = None,
    limit: int = 100,
) -> dict:
    """Get OHLCV kline data with forward-fill for empty intervals."""
    if interval not in KLINE_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval '{interval}'. Valid: {', '.join(KLINE_INTERVALS.keys())}",
        )

    interval_seconds = KLINE_INTERVALS[interval]
    db = get_db()
    symbol_upper = symbol.upper()

    et_filter = ""
    params: list = [symbol_upper, interval_seconds, limit]
    if engine_type is not None:
        et_filter = "AND t.engine_type = $4"
        params.append(engine_type)

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
        return {"symbol": symbol_upper, "interval": interval, "klines": []}

    raw_candles.reverse()

    candle_map = {}
    for c in raw_candles:
        candle_map[int(c["bucket"])] = c

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

    return {"symbol": symbol_upper, "interval": interval, "klines": klines}
