"""
Orderbook domain service — CLOB order management, queries, trade history.
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException

from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType


async def get_orderbook_markets(router: EngineRouter, symbol: Optional[str] = None, levels: int = 20) -> dict:
    """List CLOB markets or get single orderbook."""
    if symbol:
        symbol_upper = symbol.upper()
        engine = await router._get_engine(symbol_upper, EngineType.CLOB)
        if not engine:
            raise HTTPException(status_code=404, detail=f"CLOB market '{symbol}' not found")
        order_book = await engine._get_order_book(levels)
        return {
            "symbol": symbol_upper,
            "bids": order_book["bids"],
            "asks": order_book["asks"],
        }

    db = get_db()
    markets = await db.read(
        """
        SELECT sc.*
        FROM symbol_configs sc
        WHERE sc.engine_type = 1 AND sc.is_active = TRUE
        ORDER BY sc.symbol
        """
    )
    result = []
    for market in markets:
        best_bid = await db.read_one(
            """
            SELECT price FROM orderbook_orders
            WHERE symbol_id = $1 AND side = 0 AND status IN (0, 1)
            ORDER BY price DESC LIMIT 1
            """,
            market["symbol_id"],
        )
        best_ask = await db.read_one(
            """
            SELECT price FROM orderbook_orders
            WHERE symbol_id = $1 AND side = 1 AND status IN (0, 1)
            ORDER BY price ASC LIMIT 1
            """,
            market["symbol_id"],
        )
        result.append({
            **market,
            "best_bid": float(best_bid["price"]) if best_bid else None,
            "best_ask": float(best_ask["price"]) if best_ask else None,
        })
    return {"markets": result, "count": len(result)}


async def get_trades(symbol: str, limit: int = 100) -> dict:
    """Get recent CLOB trades for a symbol."""
    db = get_db()
    trades = await db.read(
        """
        SELECT t.trade_id, t.side, t.price, t.quantity, t.quote_amount,
               t.fee_amount, t.fee_asset, t.created_at
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.symbol = $1 AND sc.engine_type = 1 AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        symbol.upper(),
        limit,
    )
    return {"symbol": symbol.upper(), "trades": trades}


async def get_quote(router: EngineRouter, symbol: str, side: OrderSide, quantity: Decimal) -> dict:
    """Get quote for a market order."""
    result = await router.get_quote(
        symbol=symbol.upper(),
        side=side,
        quantity=quantity,
        engine_type=EngineType.CLOB,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    return {
        "symbol": symbol.upper(),
        "side": side.value,
        "quantity": float(quantity),
        "estimated_avg_price": float(result.effective_price),
        "estimated_total": float(result.output_amount) if side == OrderSide.SELL else float(result.input_amount),
        "fee_amount": float(result.fee_amount),
        "fee_asset": result.fee_asset,
    }


async def place_order(
    router: EngineRouter,
    user_id: str,
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    quantity: Decimal,
    price: Optional[Decimal] = None,
) -> dict:
    """Place an order on the CLOB orderbook."""
    result = await router.execute_trade(
        user_id=user_id,
        symbol=symbol.upper(),
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type,
        engine_type=EngineType.CLOB,
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    return {
        "order_id": str(result.order_id) if result.order_id else None,
        "trade_id": str(result.trade_id) if result.trade_id else None,
        "symbol": symbol.upper(),
        "side": result.side.value,
        "order_type": order_type.value,
        "price": float(price) if price else float(result.price),
        "quantity": float(quantity),
        "filled_quantity": float(result.quantity),
        "status": result.status.value,
        "fills": result.fills,
    }


async def cancel_order(router: EngineRouter, user_id: str, symbol: str, order_id: str) -> dict:
    """Cancel an open order."""
    engine = await router._get_engine(symbol.upper(), EngineType.CLOB)
    if not engine:
        raise HTTPException(status_code=404, detail=f"CLOB market '{symbol}' not found")

    result = await engine.cancel_order(user_id, order_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to cancel order"))

    return result


async def get_user_orders(
    user_id: str,
    symbol: str,
    status: Optional[List[OrderStatus]] = None,
    limit: int = 50,
) -> dict:
    """Get user's orders for a specific CLOB market."""
    db = get_db()

    query = """
        SELECT o.*, sc.symbol FROM orderbook_orders o
        JOIN symbol_configs sc USING (symbol_id)
        WHERE o.user_id = $1 AND sc.symbol = $2 AND sc.engine_type = 1
    """
    params: list = [user_id, symbol.upper()]
    param_idx = 3

    if status:
        status_values = [s.value for s in status]
        query += f" AND o.status = ANY(${param_idx})"
        params.append(status_values)
        param_idx += 1

    query += f" ORDER BY o.created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    orders = await db.read(query, *params)
    return {"symbol": symbol.upper(), "orders": orders}


async def get_all_user_orders(
    user_id: str,
    symbol: Optional[str] = None,
    status: Optional[List[OrderStatus]] = None,
    limit: int = 50,
) -> list:
    """Get all user's orders across CLOB markets."""
    db = get_db()

    query = """
        SELECT o.*, sc.symbol FROM orderbook_orders o
        JOIN symbol_configs sc USING (symbol_id)
        WHERE o.user_id = $1 AND sc.engine_type = 1
    """
    params: list = [user_id]
    param_idx = 2

    if symbol:
        query += f" AND sc.symbol = ${param_idx}"
        params.append(symbol.upper())
        param_idx += 1

    if status:
        status_values = [s.value for s in status]
        query += f" AND o.status = ANY(${param_idx})"
        params.append(status_values)
        param_idx += 1

    query += f" ORDER BY o.created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    return await db.read(query, *params)
