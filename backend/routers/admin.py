"""
Admin API Routes

Operations for system administrators.
"""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType, SymbolStatus
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_router() -> EngineRouter:
    """Dependency to get engine router"""
    return EngineRouter(get_db())


@router.post("/init-pool", response_model=APIResponse)
async def initialize_amm_pool(
    symbol: str = Query(..., description="Symbol to initialize"),
    reserve_base: Decimal = Query(..., description="Initial base asset reserve"),
    reserve_quote: Decimal = Query(..., description="Initial quote asset reserve"),
    router: EngineRouter = Depends(get_router),
):
    """
    Initialize or reset an AMM pool with specified reserves.

    Admin only - used to set up initial liquidity.
    """
    db = get_db()

    # Get symbol config
    config = await db.read_one(
        "SELECT * FROM symbol_configs WHERE symbol = $1",
        symbol.upper(),
    )

    if not config:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if config["engine_type"] != EngineType.AMM:
        raise HTTPException(status_code=400, detail="Symbol is not an AMM type")

    # Update or create pool
    k_value = reserve_base * reserve_quote

    result = await db.execute_returning(
        """
        INSERT INTO amm_pools (symbol_config_id, reserve_base, reserve_quote, k_value)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (symbol_config_id)
        DO UPDATE SET
            reserve_base = $2,
            reserve_quote = $3,
            k_value = $4,
            updated_at = NOW()
        RETURNING *
        """,
        config["id"],
        reserve_base,
        reserve_quote,
        k_value,
    )

    router.invalidate_cache(symbol.upper())

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "reserve_base": float(reserve_base),
            "reserve_quote": float(reserve_quote),
            "k_value": float(k_value),
            "current_price": float(reserve_quote / reserve_base) if reserve_base > 0 else 0,
        },
    )


@router.post("/seed-orderbook", response_model=APIResponse)
async def seed_orderbook(
    symbol: str = Query(..., description="Symbol to seed"),
    mid_price: Decimal = Query(..., description="Middle price"),
    spread_pct: Decimal = Query(default=Decimal("0.5"), description="Spread percentage"),
    levels: int = Query(default=10, description="Number of price levels"),
    quantity_per_level: Decimal = Query(default=Decimal("10"), description="Quantity per level"),
    admin_user_id: UUID = Query(..., description="Admin user ID to own the orders"),
):
    """
    Seed an order book with initial orders.

    Creates buy and sell orders around a mid price for testing.
    Admin only.
    """
    db = get_db()

    # Get symbol config
    config = await db.read_one(
        "SELECT * FROM symbol_configs WHERE symbol = $1",
        symbol.upper(),
    )

    if not config:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if config["engine_type"] != EngineType.CLOB:
        raise HTTPException(status_code=400, detail="Symbol is not a CLOB type")

    # Calculate price levels
    spread = mid_price * spread_pct / 100
    tick = spread / levels

    orders_created = 0

    # Create buy orders (below mid price)
    for i in range(levels):
        price = mid_price - spread / 2 - (tick * i)

        await db.execute(
            """
            INSERT INTO orderbook_orders (
                symbol_config_id, user_id, side, order_type,
                price, quantity, remaining_quantity, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $6, $7)
            """,
            config["id"],
            admin_user_id,
            OrderSide.BUY.value,
            OrderType.LIMIT.value,
            price,
            quantity_per_level,
            OrderStatus.OPEN.value,
        )
        orders_created += 1

    # Create sell orders (above mid price)
    for i in range(levels):
        price = mid_price + spread / 2 + (tick * i)

        await db.execute(
            """
            INSERT INTO orderbook_orders (
                symbol_config_id, user_id, side, order_type,
                price, quantity, remaining_quantity, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $6, $7)
            """,
            config["id"],
            admin_user_id,
            OrderSide.SELL.value,
            OrderType.LIMIT.value,
            price,
            quantity_per_level,
            OrderStatus.OPEN.value,
        )
        orders_created += 1

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "orders_created": orders_created,
            "mid_price": float(mid_price),
            "spread_pct": float(spread_pct),
            "levels": levels,
        },
    )


@router.post("/credit-balance", response_model=APIResponse)
async def credit_user_balance(
    user_id: UUID = Query(..., description="User ID"),
    asset: str = Query(..., description="Asset to credit"),
    amount: Decimal = Query(..., description="Amount to credit"),
):
    """
    Credit a user's balance.

    Admin only - for testing or customer support.
    """
    db = get_db()

    # Check if balance exists
    existing = await db.read_one(
        "SELECT id FROM user_balances WHERE user_id = $1 AND asset = $2",
        user_id,
        asset.upper(),
    )

    if existing:
        await db.execute(
            """
            UPDATE user_balances
            SET available = available + $3, updated_at = NOW()
            WHERE user_id = $1 AND asset = $2
            """,
            user_id,
            asset.upper(),
            amount,
        )
    else:
        await db.execute(
            """
            INSERT INTO user_balances (user_id, asset, available, locked)
            VALUES ($1, $2, $3, 0)
            """,
            user_id,
            asset.upper(),
            amount,
        )

    # Get updated balance
    balance = await db.read_one(
        """
        SELECT asset, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1 AND asset = $2
        """,
        user_id,
        asset.upper(),
    )

    return APIResponse(success=True, data=balance)


@router.get("/stats", response_model=APIResponse)
async def get_system_stats():
    """
    Get system-wide statistics.

    Admin only.
    """
    db = get_db()

    # User count
    user_count = await db.read_one("SELECT COUNT(*) as count FROM users")

    # Trade count by engine
    trade_stats = await db.read(
        """
        SELECT engine_type, COUNT(*) as count, SUM(quote_amount) as volume
        FROM trades
        GROUP BY engine_type
        """
    )

    # Active symbols
    symbol_count = await db.read_one(
        f"SELECT COUNT(*) as count FROM symbol_configs WHERE status = {SymbolStatus.ACTIVE}"
    )

    # Open orders
    open_orders = await db.read_one(
        f"SELECT COUNT(*) as count FROM orderbook_orders WHERE status IN ({OrderStatus.OPEN}, {OrderStatus.PARTIAL})"
    )

    return APIResponse(
        success=True,
        data={
            "users": user_count["count"],
            "active_symbols": symbol_count["count"],
            "open_orders": open_orders["count"],
            "trades_by_engine": trade_stats,
        },
    )


@router.delete("/clear-orders", response_model=APIResponse)
async def clear_all_orders(
    symbol: str = Query(..., description="Symbol to clear orders for"),
    router: EngineRouter = Depends(get_router),
):
    """
    Clear all open orders for a symbol.

    Admin only - use with caution!
    """
    db = get_db()

    # Get symbol config
    config = await db.read_one(
        "SELECT id FROM symbol_configs WHERE symbol = $1",
        symbol.upper(),
    )

    if not config:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    # Cancel all open orders
    result = await db.execute(
        f"""
        UPDATE orderbook_orders
        SET status = {OrderStatus.CANCELLED}, cancelled_at = NOW()
        WHERE symbol_config_id = $1 AND status IN ({OrderStatus.OPEN}, {OrderStatus.PARTIAL})
        """,
        config["id"],
    )

    # Extract count from result
    count = int(result.split()[-1]) if result else 0

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "orders_cancelled": count,
        },
    )
