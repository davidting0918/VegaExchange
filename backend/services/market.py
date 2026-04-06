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
    """Get OHLCV kline data from pre-computed klines table."""
    from backend.services.kline import SUPPORTED_INTERVALS, get_klines as kline_get

    if interval not in SUPPORTED_INTERVALS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid interval '{interval}'. Valid: {', '.join(SUPPORTED_INTERVALS.keys())}",
        )

    db = get_db()
    symbol_upper = symbol.upper()

    # Resolve symbol_id and engine_type
    if engine_type is not None:
        sym = await db.read_one(
            "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = $2",
            symbol_upper, engine_type,
        )
    else:
        sym = await db.read_one(
            "SELECT symbol_id, engine_type FROM symbol_configs WHERE symbol = $1 AND is_active = TRUE LIMIT 1",
            symbol_upper,
        )
        if sym:
            engine_type = sym["engine_type"]

    if not sym:
        return {"symbol": symbol_upper, "interval": interval, "klines": []}

    rows = await kline_get(sym["symbol_id"], engine_type, interval, limit)

    klines = [
        {
            "time": int(r["open_time"].timestamp()) if hasattr(r["open_time"], "timestamp") else r["open_time"],
            "open": r["open"],
            "high": r["high"],
            "low": r["low"],
            "close": r["close"],
            "volume": r["volume"],
            "quote_volume": r["quote_volume"],
            "trade_count": r["trade_count"],
        }
        for r in rows
    ]

    return {"symbol": symbol_upper, "interval": interval, "klines": klines}


async def get_ticker(symbol: str, engine_type: Optional[int] = None) -> dict:
    """Get 24h ticker stats from 1h klines (24 rows)."""
    from backend.services.kline import get_24h_ticker

    db = get_db()
    symbol_upper = symbol.upper()

    if engine_type is not None:
        sym = await db.read_one(
            "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = $2",
            symbol_upper, engine_type,
        )
    else:
        sym = await db.read_one(
            "SELECT symbol_id, engine_type FROM symbol_configs WHERE symbol = $1 AND is_active = TRUE LIMIT 1",
            symbol_upper,
        )
        if sym:
            engine_type = sym["engine_type"]

    if not sym:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    ticker = await get_24h_ticker(sym["symbol_id"], engine_type)
    ticker["symbol"] = symbol_upper
    return ticker


async def get_all_tickers() -> list:
    """Get 24h ticker stats for all active symbols."""
    from backend.services.kline import get_24h_ticker

    db = get_db()
    symbols = await db.read(
        "SELECT symbol_id, symbol, engine_type FROM symbol_configs WHERE is_active = TRUE"
    )

    tickers = []
    for sym in symbols:
        ticker = await get_24h_ticker(sym["symbol_id"], sym["engine_type"])
        ticker["symbol"] = sym["symbol"]
        ticker["engine_type"] = sym["engine_type"]
        tickers.append(ticker)

    return tickers
