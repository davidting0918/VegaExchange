"""
Pool domain service — AMM pool queries, swap, liquidity, charts.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException

from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide
from backend.models.pool import (
    PeriodKind,
    parse_symbol_path,
    parse_symbol_path_components,
    parse_symbol_string,
)


def _enrich_with_components(data: dict, symbol_path: str) -> dict:
    """Add base/quote/settle/market components to response data if parseable."""
    components = parse_symbol_path_components(symbol_path)
    if components:
        data["base"], data["quote"], data["settle"], data["market"] = components
    return data


def _chart_since_and_bucket(period: PeriodKind) -> tuple[datetime, str]:
    """Return (since_ts in UTC, PostgreSQL date_trunc bucket part)."""
    now = datetime.now(timezone.utc)
    mapping = {
        "1H": (timedelta(hours=1), "5min"),
        "1D": (timedelta(days=1), "hour"),
        "1W": (timedelta(weeks=1), "day"),
        "1M": (timedelta(days=30), "day"),
        "1Y": (timedelta(days=365), "day"),
        "ALL": (timedelta(days=365), "day"),
    }
    delta, bucket = mapping[period]
    return now - delta, bucket


# =============================================================================
# Pool Queries
# =============================================================================

async def list_pools(router: EngineRouter, symbol: Optional[str] = None) -> dict:
    """List all AMM pools or get single pool data."""
    if symbol:
        symbol_str = parse_symbol_path(symbol)
        engine = await router._get_engine(symbol_str, EngineType.AMM)
        if not engine:
            raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")
        pool = await engine._get_pool()
        if not pool:
            raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")
        data = {
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
        return _enrich_with_components(data, symbol)

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
    return {"pools": pools, "count": len(pools)}


async def get_pool_trades(symbol: str, limit: int = 100) -> dict:
    """Get recent AMM trades for a symbol."""
    symbol_str = parse_symbol_path(symbol)
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

    data: dict = {"symbol": symbol_str, "trades": trades}
    return _enrich_with_components(data, symbol)


async def get_pool_user(router: EngineRouter, user_id: str, symbol: str) -> dict:
    """Get user LP position + base/quote balances for a pool."""
    symbol_str = parse_symbol_path(symbol)
    engine = await router._get_engine(symbol_str, EngineType.AMM)
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol_str}'")

    position = await engine._get_lp_position(user_id)

    db = get_db()
    base_row = await db.read_one(
        "SELECT available FROM user_balances WHERE user_id = $1 AND currency = $2 AND account_type = 'spot' AND is_active = TRUE",
        user_id, engine.base_asset,
    )
    quote_row = await db.read_one(
        "SELECT available FROM user_balances WHERE user_id = $1 AND currency = $2 AND account_type = 'spot' AND is_active = TRUE",
        user_id, engine.quote_asset,
    )

    base_balance = float(base_row["available"]) if base_row else 0
    quote_balance = float(quote_row["available"]) if quote_row else 0

    lp_data = None
    if position and float(position.get("lp_shares", 0)) > 0:
        pool_data = await engine._get_pool()
        user_lp = Decimal(str(position["lp_shares"]))
        if pool_data:
            total_lp = Decimal(str(pool_data["total_lp_shares"]))
            rb = Decimal(str(pool_data["reserve_base"]))
            rq = Decimal(str(pool_data["reserve_quote"]))
            share_ratio = user_lp / total_lp if total_lp > 0 else Decimal("0")
            estimated_base = rb * share_ratio
            estimated_quote = rq * share_ratio
        else:
            share_ratio = estimated_base = estimated_quote = Decimal("0")

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
    return _enrich_with_components(data, symbol)


# =============================================================================
# Charts
# =============================================================================

async def get_volume_chart(symbol: str, period: PeriodKind, limit: int = 100) -> dict:
    """Get time-bucketed volume for a pool."""
    symbol_str = parse_symbol_path(symbol)
    db = get_db()

    row = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = 0 AND is_active = TRUE",
        symbol_str,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    symbol_id = row["symbol_id"]
    since_ts, bucket_kind = _chart_since_and_bucket(period)

    if bucket_kind == "5min":
        bucket_sql = (
            "date_trunc('hour', t.created_at) + "
            "(floor(extract(minute from t.created_at) / 5) * interval '5 minutes')"
        )
    else:
        bucket_sql = f"date_trunc('{bucket_kind}', t.created_at)"

    rows = await db.read(
        f"""
        SELECT {bucket_sql} AS bucket,
               COALESCE(SUM(t.quote_amount), 0) AS volume
        FROM trades t
        WHERE t.symbol_id = $1 AND t.engine_type = 0 AND t.status = 1
          AND t.created_at >= $2
        GROUP BY {bucket_sql}
        ORDER BY bucket ASC
        LIMIT $3
        """,
        symbol_id, since_ts, limit,
    )

    buckets = [
        {
            "time": r["bucket"].isoformat() if hasattr(r["bucket"], "isoformat") else str(r["bucket"]),
            "volume": float(r["volume"]),
        }
        for r in rows
    ]

    data: dict = {"symbol": symbol_str, "buckets": buckets}
    return _enrich_with_components(data, symbol)


async def get_price_history(symbol: str, period: PeriodKind, limit: int = 500) -> dict:
    """Get price history for a pool from AMM reserve snapshots."""
    symbol_str = parse_symbol_path(symbol)
    db = get_db()

    row = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = 0 AND is_active = TRUE",
        symbol_str,
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_str}' not found")

    since_ts, _ = _chart_since_and_bucket(period)

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
        ORDER BY t.created_at ASC
        LIMIT $3
        """,
        row["symbol_id"], since_ts, limit,
    )

    prices = [
        {
            "time": r["time"].isoformat() if hasattr(r["time"], "isoformat") else str(r["time"]),
            "price": float(r["price"]),
        }
        for r in rows
    ]

    data: dict = {"symbol": symbol_str, "prices": prices}
    return _enrich_with_components(data, symbol)


# =============================================================================
# Trading Operations (delegate to engine)
# =============================================================================

async def get_swap_quote(
    router: EngineRouter,
    symbol: str,
    side: OrderSide,
    quantity: Optional[Decimal] = None,
    quote_amount: Optional[Decimal] = None,
) -> dict:
    """Get quote for an AMM swap."""
    symbol_str = parse_symbol_path(symbol)
    result = await router.get_quote(
        symbol=symbol_str, side=side, quantity=quantity,
        quote_amount=quote_amount, engine_type=EngineType.AMM,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    data: dict = {
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
    return _enrich_with_components(data, symbol)


async def get_add_liquidity_quote(
    router: EngineRouter,
    symbol: str,
    base_amount: Optional[Decimal] = None,
    quote_amount: Optional[Decimal] = None,
) -> dict:
    """Get quote for adding liquidity — calculates required counterpart amount."""
    if base_amount is None and quote_amount is None:
        raise HTTPException(status_code=400, detail="Provide either base_amount or quote_amount")
    if base_amount is not None and quote_amount is not None:
        raise HTTPException(status_code=400, detail="Provide only one of base_amount or quote_amount")

    symbol_str = parse_symbol_path(symbol)
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
        data: dict = {"base_amount": float(base_amount), "quote_amount": float(base_amount * ratio)}
    else:
        data = {"base_amount": float(quote_amount / ratio), "quote_amount": float(quote_amount)}

    return _enrich_with_components(data, symbol)


async def execute_swap(router: EngineRouter, user_id: str, symbol: str, side: OrderSide, amount_in: Decimal, min_amount_out: Optional[Decimal] = None) -> dict:
    """Execute an AMM swap."""
    symbol_upper = symbol.upper()

    if side == OrderSide.BUY:
        quantity, qa = None, amount_in
    else:
        quantity, qa = amount_in, None

    result = await router.execute_trade(
        user_id=user_id, symbol=symbol_upper, side=side,
        quantity=quantity, quote_amount=qa,
        min_amount_out=min_amount_out, engine_type=EngineType.AMM,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    data: dict = {
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
        data["base"], data["quote"], data["settle"], data["market"] = components
    return data


async def add_liquidity(router: EngineRouter, user_id: str, symbol: str, base_amount: Decimal, quote_amount: Decimal) -> dict:
    """Add liquidity to an AMM pool."""
    symbol_upper = symbol.upper()
    engine = await router._get_engine(symbol_upper, EngineType.AMM)
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_upper}' not found")

    result = await engine.add_liquidity(user_id=user_id, base_amount=base_amount, quote_amount=quote_amount)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add liquidity"))

    data: dict = {
        "symbol": symbol_upper,
        "lp_shares": result["lp_shares"],
        "pool_id": result["pool_id"],
        "reserve_base": result["reserve_base"],
        "reserve_quote": result["reserve_quote"],
        "total_lp_shares": result["total_lp_shares"],
    }
    components = parse_symbol_string(symbol_upper)
    if components:
        data["base"], data["quote"], data["settle"], data["market"] = components
    return data


async def remove_liquidity(router: EngineRouter, user_id: str, symbol: str, lp_shares: Decimal) -> dict:
    """Remove liquidity from an AMM pool."""
    symbol_upper = symbol.upper()
    engine = await router._get_engine(symbol_upper, EngineType.AMM)
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol_upper}' not found")

    result = await engine.remove_liquidity(user_id=user_id, lp_shares=lp_shares)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove liquidity"))

    data: dict = {
        "symbol": symbol_upper,
        "base_out": result["base_out"],
        "quote_out": result["quote_out"],
        "lp_shares_burned": result["lp_shares_burned"],
        "remaining_lp_shares": result["remaining_lp_shares"],
        "pool_id": result["pool_id"],
        "reserve_base": result["reserve_base"],
        "reserve_quote": result["reserve_quote"],
        "total_lp_shares": result["total_lp_shares"],
    }
    components = parse_symbol_string(symbol_upper)
    if components:
        data["base"], data["quote"], data["settle"], data["market"] = components
    return data


async def get_lp_history(router: EngineRouter, user_id: str, symbol: str) -> dict:
    """Get user's LP event history."""
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
        pool["pool_id"], user_id,
    )

    formatted = [
        {
            "id": e["id"],
            "event_type": e["event_type"],
            "lp_shares": float(e["lp_shares"]),
            "base_amount": float(e["base_amount"]),
            "quote_amount": float(e["quote_amount"]),
            "created_at": e["created_at"].isoformat() if e["created_at"] else None,
        }
        for e in events
    ]

    data: dict = {"symbol": symbol_str, "events": formatted}
    return _enrich_with_components(data, symbol)


# =============================================================================
# Shared helpers (used by both pool and admin routers)
# =============================================================================

async def get_all_pools_enriched() -> List[dict]:
    """Get all AMM pools with calculated price and TVL. Used by admin and pool list."""
    db = get_db()
    return await db.read(
        """
        SELECT
            ap.pool_id, sc.symbol, sc.symbol_id, sc.base, sc.quote,
            ap.reserve_base, ap.reserve_quote, ap.k_value, ap.fee_rate,
            ap.total_lp_shares, ap.total_volume_base, ap.total_volume_quote,
            ap.total_fees_collected, ap.is_active,
            CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE 0 END as price,
            ap.reserve_quote * 2 as tvl_usdt,
            ap.created_at, ap.updated_at
        FROM amm_pools ap
        JOIN symbol_configs sc ON ap.symbol_id = sc.symbol_id
        ORDER BY ap.reserve_quote * 2 DESC
        """
    )


async def get_pool_detail(pool_id: str) -> dict:
    """Get pool info + LP positions + recent swaps. Used by admin pool detail."""
    db = get_db()

    pool = await db.read_one(
        """
        SELECT
            ap.*, sc.symbol, sc.base, sc.quote, sc.market, sc.settle,
            CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE 0 END as price,
            ap.reserve_quote * 2 as tvl_usdt
        FROM amm_pools ap
        JOIN symbol_configs sc ON ap.symbol_id = sc.symbol_id
        WHERE ap.pool_id = $1
        """,
        pool_id,
    )
    if not pool:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found")

    lp_positions = await db.read(
        """
        SELECT lp.user_id, u.user_name, lp.lp_shares,
               CASE WHEN $2 > 0 THEN lp.lp_shares / $2 * 100 ELSE 0 END as share_pct
        FROM lp_positions lp
        JOIN users u ON lp.user_id = u.user_id
        WHERE lp.pool_id = $1 AND lp.lp_shares > 0
        ORDER BY lp.lp_shares DESC
        """,
        pool_id,
        pool["total_lp_shares"],
    )

    recent_swaps = await db.read(
        """
        SELECT t.trade_id, t.user_id, t.side, t.price, t.quantity,
               t.quote_amount, t.fee_amount, t.fee_asset, t.created_at
        FROM trades t
        WHERE t.symbol_id = $1 AND t.engine_type = 0 AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT 20
        """,
        pool["symbol_id"],
    )

    return {"pool": pool, "lp_positions": lp_positions, "recent_swaps": recent_swaps}
