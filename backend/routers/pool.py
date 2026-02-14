"""
AMM Pool API Routes

All AMM-specific endpoints including swaps, liquidity, and pool data.
Endpoint prefix: /api/pool
"""

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import get_current_user_id
from backend.core.balance_utils import get_user_balances as get_user_balances_util
from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide
from backend.models.requests import AddLiquidityRequest, RemoveLiquidityRequest, SwapRequest
from backend.models.responses import APIResponse
from backend.websocket_manager import broadcast_pool as ws_broadcast_pool
from backend.websocket_manager import broadcast_user as ws_broadcast_user

router = APIRouter(prefix="/api/pool", tags=["amm-pool"])


def parse_symbol_path(symbol_path: str) -> str:
    """
    Parse symbol path and build full symbol string.
    
    Input format: {BASE}-{QUOTE}-{SETTLE}-{MARKET}
    Output format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
    Example: AMM-USDT-USDT-SPOT -> AMM/USDT-USDT:SPOT
    """
    parts = symbol_path.upper().split('-')
    if len(parts) != 4:
        return symbol_path.upper()  # Return as-is if format doesn't match
    base, quote, settle, market = parts
    return f"{base}/{quote}-{settle}:{market}"


def parse_symbol_path_components(symbol_path: str) -> tuple[str, str, str, str] | None:
    """
    Parse symbol path and return (base, quote, settle, market) components.
    
    Input format: {BASE}-{QUOTE}-{SETTLE}-{MARKET}
    Example: AMM-USDT-USDT-SPOT -> ("AMM", "USDT", "USDT", "SPOT")
    """
    parts = symbol_path.upper().split('-')
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def parse_symbol_string(symbol_str: str) -> tuple[str, str, str, str] | None:
    """
    Parse symbol string and return (base, quote, settle, market) components.

    Input format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
    Example: AMM/USDT-USDT:SPOT -> ("AMM", "USDT", "USDT", "SPOT")
    """
    match = re.match(r"^([^/]+)/([^-]+)-([^:]+):(.+)$", symbol_str.upper())
    if not match:
        return None
    return match.group(1), match.group(2), match.group(3), match.group(4)


def _format_trade_for_json(t: dict) -> dict:
    """Ensure trade row is JSON-serializable (e.g. created_at to isoformat)."""
    out = dict(t)
    if "created_at" in out and hasattr(out["created_at"], "isoformat"):
        out["created_at"] = out["created_at"].isoformat()
    return out


async def _build_pool_public_data(
    symbol_str: str, engine_router: EngineRouter, limit: int = 100
) -> dict | None:
    """Build pool public payload (pool info + trades) for WebSocket broadcast."""
    engine = await engine_router._get_engine(symbol_str, EngineType.AMM)
    if not engine:
        return None
    pool = await engine._get_pool()
    if not pool:
        return None
    db = get_db()
    trades = await db.read(
        """
        SELECT t.trade_id, t.side, t.price, t.quantity, t.quote_amount,
               t.fee_amount, t.fee_asset, t.created_at
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.symbol = $1 AND sc.engine_type = 0 AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        symbol_str,
        limit,
    )
    components = parse_symbol_string(symbol_str)
    data: dict = {
        "symbol": symbol_str,
        "pool_id": pool["pool_id"],
        "reserve_base": float(pool["reserve_base"]),
        "reserve_quote": float(pool["reserve_quote"]),
        "k_value": float(pool["k_value"]),
        "fee_rate": float(pool["fee_rate"]),
        "total_volume_base": float(pool["total_volume_base"]),
        "total_volume_quote": float(pool["total_volume_quote"]),
        "total_fees_collected": float(pool["total_fees_collected"]),
        "total_lp_shares": float(pool["total_lp_shares"]),
        "current_price": float(pool["reserve_quote"]) / float(pool["reserve_base"])
        if float(pool["reserve_base"]) > 0 else 0,
        "trades": [_format_trade_for_json(t) for t in trades],
    }
    if trades:
        latest = trades[0]
        created_at = latest.get("created_at")
        time_iso = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)
        data["price_point"] = {"time": time_iso, "price": float(latest["price"])}
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    return data


async def _build_pool_user_data(
    symbol_str: str, user_id: str, engine_router: EngineRouter
) -> dict:
    """Build pool user payload (LP position + base/quote balances) for WebSocket broadcast."""
    engine = await engine_router._get_engine(symbol_str, EngineType.AMM)
    components = parse_symbol_string(symbol_str)
    empty: dict = {
        "symbol": symbol_str,
        "lp_position": None,
        "base_balance": "0",
        "quote_balance": "0",
    }
    if components:
        base, quote, settle, market = components
        empty["base"] = base
        empty["quote"] = quote
        empty["settle"] = settle
        empty["market"] = market
    if not engine:
        return empty
    pool = await engine._get_pool()
    if not pool:
        return empty
    base_asset = engine.base_asset
    quote_asset = engine.quote_asset
    position = await engine._get_lp_position(user_id)
    db = get_db()
    base_row = await db.read_one(
        """
        SELECT available FROM user_balances
        WHERE user_id = $1 AND currency = $2 AND account_type = 'spot' AND is_active = TRUE
        """,
        user_id,
        base_asset,
    )
    quote_row = await db.read_one(
        """
        SELECT available FROM user_balances
        WHERE user_id = $1 AND currency = $2 AND account_type = 'spot' AND is_active = TRUE
        """,
        user_id,
        quote_asset,
    )
    base_balance = float(base_row["available"]) if base_row else 0
    quote_balance = float(quote_row["available"]) if quote_row else 0
    lp_data: dict | None = None
    if position and float(position.get("lp_shares", 0)) > 0:
        user_lp = Decimal(str(position["lp_shares"]))
        total_lp = Decimal(str(pool["total_lp_shares"]))
        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))
        if total_lp > 0:
            share_ratio = user_lp / total_lp
            estimated_base = reserve_base * share_ratio
            estimated_quote = reserve_quote * share_ratio
        else:
            share_ratio = Decimal("0")
            estimated_base = Decimal("0")
            estimated_quote = Decimal("0")
        lp_data = {
            "pool_id": str(position.get("pool_id", "")),
            "lp_shares": float(position["lp_shares"]),
            "share_percentage": float(share_ratio),
            "estimated_base_value": float(estimated_base),
            "estimated_quote_value": float(estimated_quote),
            "initial_base_amount": float(position.get("initial_base_amount", 0)),
            "initial_quote_amount": float(position.get("initial_quote_amount", 0)),
        }
    data: dict = {
        "symbol": symbol_str,
        "lp_position": lp_data,
        "base_balance": str(base_balance),
        "quote_balance": str(quote_balance),
    }
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    return data


async def _broadcast_pool_and_user(
    symbol_str: str, user_id: str, engine_router: EngineRouter
) -> None:
    """After a pool mutation, broadcast pool and user updates over WebSocket."""
    pool_data = await _build_pool_public_data(symbol_str, engine_router)
    if pool_data:
        await ws_broadcast_pool(symbol_str, pool_data)
    pool_user_data = await _build_pool_user_data(symbol_str, user_id, engine_router)
    balances = await get_user_balances_util(user_id, include_total=True)
    balances_list = [
        {
            "currency": b["currency"],
            "available": float(b["available"]),
            "locked": float(b["locked"]),
            "total": float(b.get("total", b["available"] + b["locked"])),
        }
        for b in balances
    ]
    await ws_broadcast_user(
        user_id,
        {"balances": balances_list, "pool_user": pool_user_data},
    )


@router.get("", response_model=APIResponse)
async def list_pools(
    symbol: Optional[str] = Query(None, description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    router: EngineRouter = Depends(get_router),
):
    """
    List all active AMM pools, or get a single pool when symbol is provided.
    
    Query param: symbol - optional. When provided, returns single pool data.
    """
    if symbol:
        symbol_str = parse_symbol_path(symbol)
        components = parse_symbol_path_components(symbol)
        engine = await router._get_engine(symbol_str, EngineType.AMM)
        if not engine:
            raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")
        pool = await engine._get_pool()
        if not pool:
            raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")
        data: dict = {
            "symbol": symbol_str,
            "pool_id": pool["pool_id"],
            "reserve_base": float(pool["reserve_base"]),
            "reserve_quote": float(pool["reserve_quote"]),
            "k_value": float(pool["k_value"]),
            "fee_rate": float(pool["fee_rate"]),
            "total_volume_base": float(pool["total_volume_base"]),
            "total_volume_quote": float(pool["total_volume_quote"]),
            "total_fees_collected": float(pool["total_fees_collected"]),
            "total_lp_shares": float(pool["total_lp_shares"]),
            "current_price": float(pool["reserve_quote"]) / float(pool["reserve_base"])
            if float(pool["reserve_base"]) > 0 else 0,
        }
        if components:
            base, quote, settle, market = components
            data["base"] = base
            data["quote"] = quote
            data["settle"] = settle
            data["market"] = market
        return APIResponse(success=True, data=data)

    db = get_db()
    pools = await db.read(
        """
        SELECT sc.symbol, sc.symbol_id, sc.base, sc.quote, sc.settle, sc.market,
               ap.pool_id, ap.reserve_base, ap.reserve_quote, ap.k_value, 
               ap.fee_rate, ap.total_lp_shares, ap.total_volume_base, ap.total_volume_quote,
               ap.total_fees_collected,
               CASE WHEN ap.reserve_base > 0 
                    THEN ap.reserve_quote / ap.reserve_base 
                    ELSE 0 END as current_price
        FROM symbol_configs sc
        JOIN amm_pools ap ON sc.symbol_id = ap.symbol_id
        WHERE sc.engine_type = 0 AND sc.is_active = TRUE
        ORDER BY sc.symbol
        """
    )
    return APIResponse(
        success=True,
        data={
            "pools": pools,
            "count": len(pools),
        },
    )


@router.get("/trades", response_model=APIResponse)
async def get_pool_trades(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    limit: int = Query(100, ge=1, le=200, description="Number of recent trades"),
):
    """
    Get recent AMM trades for a symbol.
    """
    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    db = get_db()
    
    trades = await db.read(
        """
        SELECT t.trade_id, t.side, t.price, t.quantity, t.quote_amount,
               t.fee_amount, t.fee_asset, t.created_at
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.symbol = $1 AND sc.engine_type = 0 AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        symbol_str,
        limit,
    )
    
    trades_data: dict = {
        "symbol": symbol_str,
        "trades": trades,
    }
    if components:
        base, quote, settle, market = components
        trades_data["base"] = base
        trades_data["quote"] = quote
        trades_data["settle"] = settle
        trades_data["market"] = market
    return APIResponse(success=True, data=trades_data)


@router.get("/public", response_model=APIResponse)
async def get_pool_public(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    limit: int = Query(100, ge=1, le=200, description="Number of recent trades"),
    engine_router: EngineRouter = Depends(get_router),
):
    """
    Get public pool data + recent trades in one call. No auth required.
    Reduces API calls by combining pool info and trades.
    """
    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    engine = await engine_router._get_engine(symbol_str, EngineType.AMM)

    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")

    db = get_db()
    trades = await db.read(
        """
        SELECT t.trade_id, t.side, t.price, t.quantity, t.quote_amount,
               t.fee_amount, t.fee_asset, t.created_at
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.symbol = $1 AND sc.engine_type = 0 AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        symbol_str,
        limit,
    )

    data: dict = {
        "symbol": symbol_str,
        "pool_id": pool["pool_id"],
        "reserve_base": float(pool["reserve_base"]),
        "reserve_quote": float(pool["reserve_quote"]),
        "k_value": float(pool["k_value"]),
        "fee_rate": float(pool["fee_rate"]),
        "total_volume_base": float(pool["total_volume_base"]),
        "total_volume_quote": float(pool["total_volume_quote"]),
        "total_fees_collected": float(pool["total_fees_collected"]),
        "total_lp_shares": float(pool["total_lp_shares"]),
        "current_price": float(pool["reserve_quote"]) / float(pool["reserve_base"])
        if float(pool["reserve_base"]) > 0 else 0,
        "trades": trades,
    }
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    return APIResponse(success=True, data=data)


@router.get("/user", response_model=APIResponse)
async def get_pool_user(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get user-specific pool data: LP position + base/quote balances.
    Requires authentication.
    """
    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    engine = await router._get_engine(symbol_str, EngineType.AMM)

    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")

    base_asset = engine.base_asset
    quote_asset = engine.quote_asset

    # Get LP position
    position = await engine._get_lp_position(user_id)

    # Get user balances for base and quote
    db = get_db()
    base_row = await db.read_one(
        """
        SELECT available FROM user_balances
        WHERE user_id = $1 AND currency = $2 AND account_type = 'spot' AND is_active = TRUE
        """,
        user_id,
        base_asset,
    )
    quote_row = await db.read_one(
        """
        SELECT available FROM user_balances
        WHERE user_id = $1 AND currency = $2 AND account_type = 'spot' AND is_active = TRUE
        """,
        user_id,
        quote_asset,
    )

    base_balance = float(base_row["available"]) if base_row else 0
    quote_balance = float(quote_row["available"]) if quote_row else 0

    lp_data: dict | None = None
    if position and float(position.get("lp_shares", 0)) > 0:
        pool_data = await engine._get_pool()
        user_lp = Decimal(str(position["lp_shares"]))
        if pool_data:
            total_lp = Decimal(str(pool_data["total_lp_shares"]))
            reserve_base = Decimal(str(pool_data["reserve_base"]))
            reserve_quote = Decimal(str(pool_data["reserve_quote"]))
            if total_lp > 0:
                share_ratio = user_lp / total_lp
                estimated_base = reserve_base * share_ratio
                estimated_quote = reserve_quote * share_ratio
            else:
                share_ratio = Decimal("0")
                estimated_base = Decimal("0")
                estimated_quote = Decimal("0")
        else:
            share_ratio = Decimal("0")
            estimated_base = Decimal("0")
            estimated_quote = Decimal("0")
        lp_data = {
            "pool_id": str(position.get("pool_id", "")),
            "lp_shares": float(position["lp_shares"]),
            "share_percentage": float(share_ratio),
            "estimated_base_value": float(estimated_base),
            "estimated_quote_value": float(estimated_quote),
            "initial_base_amount": float(position.get("initial_base_amount", 0)),
            "initial_quote_amount": float(position.get("initial_quote_amount", 0)),
        }

    data: dict = {
        "symbol": symbol_str,
        "lp_position": lp_data,
        "base_balance": str(base_balance),
        "quote_balance": str(quote_balance),
    }
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    return APIResponse(success=True, data=data)


PeriodKind = Literal["1H", "1D", "1W", "1M", "1Y", "ALL"]


def _chart_since_and_bucket(period: PeriodKind) -> tuple[datetime, str]:
    """Return (since_ts in UTC, PostgreSQL date_trunc bucket part for GROUP BY)."""
    now = datetime.now(timezone.utc)
    if period == "1H":
        since = now - timedelta(hours=1)
        return since, "5min"  # custom 5-min buckets
    if period == "1D":
        since = now - timedelta(days=1)
        return since, "hour"
    if period == "1W":
        since = now - timedelta(weeks=1)
        return since, "day"
    if period == "1M":
        since = now - timedelta(days=30)
        return since, "day"
    if period == "1Y":
        since = now - timedelta(days=365)
        return since, "day"
    # ALL: last 365 days
    since = now - timedelta(days=365)
    return since, "day"


@router.get("/chart/volume", response_model=APIResponse)
async def get_pool_volume_chart(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    period: PeriodKind = Query("1D", description="Time range: 1H, 1D, 1W, 1M, 1Y, ALL"),
    limit: int = Query(100, ge=1, le=500, description="Max number of buckets"),
):
    """
    Get time-bucketed volume for a pool (for bar chart).
    Public endpoint. Uses completed AMM trades only.
    """
    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    db = get_db()

    # Resolve symbol_id for this AMM symbol
    row = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = 0 AND is_active = TRUE",
        symbol_str,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    symbol_id = row["symbol_id"]
    since_ts, bucket_kind = _chart_since_and_bucket(period)

    if bucket_kind == "5min":
        # 5-minute buckets: date_trunc('hour') + floor(minute/5)*5 min
        bucket_sql = (
            "date_trunc('hour', t.created_at) + "
            "(floor(extract(minute from t.created_at) / 5) * interval '5 minutes')"
        )
    else:
        bucket_sql = f"date_trunc('{bucket_kind}', t.created_at)"

    query = f"""
        SELECT {bucket_sql} AS bucket,
               COALESCE(SUM(t.quote_amount), 0) AS volume
        FROM trades t
        WHERE t.symbol_id = $1 AND t.engine_type = 0 AND t.status = 1
          AND t.created_at >= $2
        GROUP BY {bucket_sql}
        ORDER BY bucket ASC
        LIMIT $3
    """
    rows = await db.read(query, symbol_id, since_ts, limit)

    buckets = [
        {
            "time": r["bucket"].isoformat() if hasattr(r["bucket"], "isoformat") else str(r["bucket"]),
            "volume": float(r["volume"]),
        }
        for r in rows
    ]

    data: dict = {"symbol": symbol_str, "buckets": buckets}
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    return APIResponse(success=True, data=data)


@router.get("/chart/price-history", response_model=APIResponse)
async def get_pool_price_history(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    period: PeriodKind = Query("1D", description="Time range: 1H, 1D, 1W, 1M, 1Y, ALL"),
    limit: int = Query(500, ge=1, le=2000, description="Max number of points"),
):
    """
    Get price history for a pool based on AMM pool spot prices after each trade.
    Public endpoint. Returns (time, price) series derived primarily from pool reserves,
    with a safe fallback to trade execution price when reserve data is unavailable.
    """
    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    db = get_db()

    row = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = 0 AND is_active = TRUE",
        symbol_str,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    symbol_id = row["symbol_id"]
    since_ts, _ = _chart_since_and_bucket(period)
    now_utc = datetime.now(timezone.utc)

    # Use AMM pool spot price after each trade when possible, falling back to execution price.
    # engine_data.reserve_quote_after / engine_data.reserve_base_after represents pool state
    # immediately after the trade.
    # Fetch the most recent `limit` points in the window (DESC), then reverse so chart gets ascending time.
    rows = await db.read(
        """
        SELECT 
            t.created_at AS time,
            COALESCE(
                CASE 
                    WHEN (t.engine_data ->> 'reserve_base_after') IS NOT NULL
                         AND (t.engine_data ->> 'reserve_quote_after') IS NOT NULL
                         AND NULLIF((t.engine_data ->> 'reserve_base_after')::numeric, 0) IS NOT NULL
                    THEN (t.engine_data ->> 'reserve_quote_after')::numeric 
                         / NULLIF((t.engine_data ->> 'reserve_base_after')::numeric, 0)
                    ELSE NULL
                END,
                t.price
            ) AS price
        FROM trades t
        WHERE t.symbol_id = $1 AND t.engine_type = 0 AND t.status = 1
          AND t.created_at >= $2
        ORDER BY t.created_at DESC
        LIMIT $3
        """,
        symbol_id,
        since_ts,
        limit,
    )
    rows = list(reversed(rows))  # ascending time for chart

    def _to_utc_iso(dt: datetime) -> str:
        if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).isoformat()
        return dt.replace(tzinfo=timezone.utc).isoformat()

    prices = [
        {
            "time": _to_utc_iso(r["time"]) if hasattr(r["time"], "isoformat") else str(r["time"]),
            "price": float(r["price"]),
        }
        for r in rows
    ]

    data: dict = {
        "symbol": symbol_str,
        "prices": prices,
        "range": {"from": since_ts.isoformat(), "to": now_utc.isoformat()},
    }
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    return APIResponse(success=True, data=data)


@router.get("/quote", response_model=APIResponse)
async def get_swap_quote(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Optional[Decimal] = Query(None, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get a quote for an AMM swap. Preview swap execution without actually trading.
    """
    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    result = await router.get_quote(
        symbol=symbol_str,
        side=side,
        quantity=quantity,
        quote_amount=quote_amount,
        engine_type=EngineType.AMM,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    quote_data: dict = {
        "symbol": symbol_str,
        "side": side.value,
        "input_amount": float(result.input_amount),
        "input_asset": result.input_asset,
        "output_amount": float(result.output_amount),
        "output_asset": result.output_asset,
        "effective_price": float(result.effective_price),
        "price_impact": float(result.price_impact) if result.price_impact else None,
        "fee_amount": float(result.fee_amount),
        "fee_asset": result.fee_asset,
    }
    if components:
        base, quote, settle, market = components
        quote_data["base"] = base
        quote_data["quote"] = quote
        quote_data["settle"] = settle
        quote_data["market"] = market
    return APIResponse(success=True, data=quote_data)


@router.get("/liquidity/add/quote", response_model=APIResponse)
async def get_add_liquidity_quote(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    base_amount: Optional[Decimal] = Query(None, gt=0, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, gt=0, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get quote for adding liquidity: given base_amount, returns required quote_amount (or vice versa).
    Uses pool ratio: quote_amount = base_amount * (reserve_quote / reserve_base).
    """
    if base_amount is None and quote_amount is None:
        raise HTTPException(status_code=400, detail="Provide either base_amount or quote_amount")
    if base_amount is not None and quote_amount is not None:
        raise HTTPException(status_code=400, detail="Provide only one of base_amount or quote_amount")

    symbol_str = parse_symbol_path(symbol)
    components = parse_symbol_path_components(symbol)
    engine = await router._get_engine(symbol_str, EngineType.AMM)

    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")

    reserve_base = Decimal(str(pool["reserve_base"]))
    reserve_quote = Decimal(str(pool["reserve_quote"]))

    if reserve_base <= 0:
        raise HTTPException(status_code=400, detail="Pool has no base reserve")

    ratio = reserve_quote / reserve_base
    if base_amount is not None:
        calculated_quote = base_amount * ratio
        quote_data: dict = {
            "base_amount": float(base_amount),
            "quote_amount": float(calculated_quote),
        }
    else:
        calculated_base = quote_amount / ratio
        quote_data = {
            "base_amount": float(calculated_base),
            "quote_amount": float(quote_amount),
        }

    if components:
        base, quote, settle, market = components
        quote_data["base"] = base
        quote_data["quote"] = quote
        quote_data["settle"] = settle
        quote_data["market"] = market

    return APIResponse(success=True, data=quote_data)


@router.post("/swap", response_model=APIResponse)
async def execute_swap(
    request: SwapRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Execute an AMM swap.
    
    - BUY: Spend quote asset (e.g., USDT) to get base asset
    - SELL: Sell base asset to get quote asset
    
    Symbol is provided in the request body.
    """
    symbol = request.symbol.upper()
    
    if request.side == OrderSide.BUY:
        quantity = None
        quote_amount = request.amount_in
    else:
        quantity = request.amount_in
        quote_amount = None
    
    result = await router.execute_trade(
        user_id=user_id,
        symbol=symbol,
        side=request.side,
        quantity=quantity,
        quote_amount=quote_amount,
        min_amount_out=request.min_amount_out,
        engine_type=EngineType.AMM,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    swap_data: dict = {
        "trade_id": str(result.trade_id) if result.trade_id else None,
        "symbol": result.symbol,
        "side": result.side.value,
        "price": float(result.price),
        "quantity": float(result.quantity),
        "quote_amount": float(result.quote_amount),
        "fee_amount": float(result.fee_amount),
        "price_impact": result.engine_data.get("price_impact"),
    }
    components = parse_symbol_string(result.symbol)
    if components:
        base, quote, settle, market = components
        swap_data["base"] = base
        swap_data["quote"] = quote
        swap_data["settle"] = settle
        swap_data["market"] = market
    await _broadcast_pool_and_user(result.symbol, user_id, router)
    return APIResponse(success=True, data=swap_data)


@router.post("/liquidity/add", response_model=APIResponse)
async def add_liquidity(
    request: AddLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Add liquidity to an AMM pool.
    
    Provide both base and quote assets in the correct ratio.
    Returns LP shares representing your share of the pool.
    
    Symbol is provided in the request body.
    """
    symbol = request.symbol.upper()
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    result = await engine.add_liquidity(
        user_id=user_id,
        base_amount=request.base_amount,
        quote_amount=request.quote_amount,
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add liquidity"))
    
    add_data: dict = {
        "symbol": symbol,
        "lp_shares": result["lp_shares"],
        "pool_id": result["pool_id"],
        "reserve_base": result["reserve_base"],
        "reserve_quote": result["reserve_quote"],
        "total_lp_shares": result["total_lp_shares"],
    }
    components = parse_symbol_string(symbol)
    if components:
        base, quote, settle, market = components
        add_data["base"] = base
        add_data["quote"] = quote
        add_data["settle"] = settle
        add_data["market"] = market
    await _broadcast_pool_and_user(symbol, user_id, router)
    return APIResponse(success=True, data=add_data)


@router.post("/liquidity/remove", response_model=APIResponse)
async def remove_liquidity(
    request: RemoveLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Remove liquidity from an AMM pool.
    
    Burn LP shares and receive back base and quote assets
    proportional to your share of the pool.
    
    Symbol is provided in the request body.
    """
    symbol = request.symbol.upper()
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    result = await engine.remove_liquidity(
        user_id=user_id,
        lp_shares=request.lp_shares,
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove liquidity"))
    
    remove_data: dict = {
        "symbol": symbol,
        "base_out": result["base_out"],
        "quote_out": result["quote_out"],
        "lp_shares_burned": result["lp_shares_burned"],
        "remaining_lp_shares": result["remaining_lp_shares"],
        "pool_id": result["pool_id"],
        "reserve_base": result["reserve_base"],
        "reserve_quote": result["reserve_quote"],
        "total_lp_shares": result["total_lp_shares"],
    }
    components = parse_symbol_string(symbol)
    if components:
        base, quote, settle, market = components
        remove_data["base"] = base
        remove_data["quote"] = quote
        remove_data["settle"] = settle
        remove_data["market"] = market
    await _broadcast_pool_and_user(symbol, user_id, router)
    return APIResponse(success=True, data=remove_data)


@router.get("/liquidity/position", response_model=APIResponse)
async def get_lp_position(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get your LP position for an AMM pool.
    """
    symbol_str = parse_symbol_path(symbol)
    engine = await router._get_engine(symbol_str, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")
    
    position = await engine._get_lp_position(user_id)
    
    components = parse_symbol_path_components(symbol)
    if not position:
        pos_data: dict = {
            "symbol": symbol_str,
            "lp_shares": 0,
            "has_position": False,
        }
        if components:
            base, quote, settle, market = components
            pos_data["base"] = base
            pos_data["quote"] = quote
            pos_data["settle"] = settle
            pos_data["market"] = market
        return APIResponse(success=True, data=pos_data)
    
    pool = await engine._get_pool()
    if pool:
        user_lp_shares = Decimal(str(position["lp_shares"]))
        total_lp_shares = Decimal(str(pool["total_lp_shares"]))
        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))
        
        if total_lp_shares > 0:
            share_ratio = user_lp_shares / total_lp_shares
            estimated_base_value = reserve_base * share_ratio
            estimated_quote_value = reserve_quote * share_ratio
        else:
            estimated_base_value = Decimal("0")
            estimated_quote_value = Decimal("0")
            share_ratio = Decimal("0")
    else:
        estimated_base_value = Decimal("0")
        estimated_quote_value = Decimal("0")
        share_ratio = Decimal("0")
    
    pos_data = {
        "symbol": symbol_str,
        "lp_shares": float(position["lp_shares"]),
        "initial_base_amount": float(position["initial_base_amount"]),
        "initial_quote_amount": float(position["initial_quote_amount"]),
        "estimated_base_value": float(estimated_base_value),
        "estimated_quote_value": float(estimated_quote_value),
        "pool_share_percentage": float(share_ratio),  # ratio 0-1; frontend multiplies by 100 for display
        "has_position": True,
    }
    if components:
        base, quote, settle, market = components
        pos_data["base"] = base
        pos_data["quote"] = quote
        pos_data["settle"] = settle
        pos_data["market"] = market
    return APIResponse(success=True, data=pos_data)


@router.get("/liquidity/history", response_model=APIResponse)
async def get_liquidity_history(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market (e.g. AMM-USDT-USDT-SPOT)"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get your liquidity event history for an AMM pool.
    """
    symbol_str = parse_symbol_path(symbol)
    engine = await router._get_engine(symbol_str, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")
    
    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")
    
    events = await engine.db.read(
        """
        SELECT id, pool_id, user_id, event_type, lp_shares, base_amount, quote_amount,
               pool_reserve_base, pool_reserve_quote, pool_total_lp_shares, created_at
        FROM lp_events
        WHERE pool_id = $1 AND user_id = $2
        ORDER BY created_at DESC
        """,
        pool["pool_id"],
        user_id,
    )
    
    formatted_events = []
    for event in events:
        formatted_events.append({
            "id": event["id"],
            "event_type": event["event_type"],
            "lp_shares": float(event["lp_shares"]),
            "base_amount": float(event["base_amount"]),
            "quote_amount": float(event["quote_amount"]),
            "created_at": event["created_at"].isoformat() if event["created_at"] else None,
        })
    
    history_data: dict = {
        "symbol": symbol_str,
        "events": formatted_events,
    }
    components = parse_symbol_path_components(symbol)
    if components:
        base, quote, settle, market = components
        history_data["base"] = base
        history_data["quote"] = quote
        history_data["settle"] = settle
        history_data["market"] = market
    return APIResponse(success=True, data=history_data)
