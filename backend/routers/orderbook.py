"""
CLOB Orderbook API Routes

All CLOB-specific endpoints including orders, orderbook data, and trading.
Endpoint prefix: /api/orderbook
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import get_current_user_id
from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType
from backend.models.requests import PlaceOrderRequest
from backend.models.responses import APIResponse
from backend.websocket_manager import broadcast_orderbook as ws_broadcast_orderbook

router = APIRouter(prefix="/api/orderbook", tags=["clob-orderbook"])

ORDERBOOK_WS_LEVELS = 20


@router.get("", response_model=APIResponse)
async def list_orderbook_markets(
    symbol: Optional[str] = Query(None, description="Symbol (e.g. AMM/USDT-USDT:SPOT). When provided, returns single orderbook."),
    levels: int = Query(20, ge=1, le=100, description="Number of price levels (used when symbol is provided)"),
    router: EngineRouter = Depends(get_router),
):
    """
    List all active CLOB orderbook markets, or get a single orderbook when symbol is provided.
    """
    if symbol:
        symbol_upper = symbol.upper()
        engine = await router._get_engine(symbol_upper, EngineType.CLOB)
        if not engine:
            raise HTTPException(status_code=404, detail=f"CLOB market '{symbol}' not found")
        order_book = await engine._get_order_book(levels)
        return APIResponse(
            success=True,
            data={
                "symbol": symbol_upper,
                "bids": order_book["bids"],
                "asks": order_book["asks"],
            },
        )

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
    return APIResponse(
        success=True,
        data={
            "markets": result,
            "count": len(result),
        },
    )


@router.get("/trades", response_model=APIResponse)
async def get_orderbook_trades(
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    limit: int = Query(100, ge=1, le=200, description="Number of recent trades"),
):
    """
    Get recent CLOB trades for a symbol.
    """
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
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "trades": trades,
        },
    )


@router.get("/quote", response_model=APIResponse)
async def get_order_quote(
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Decimal = Query(..., description="Amount of base asset"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get a quote for a market order on the orderbook. Preview order execution without actually trading.
    """
    result = await router.get_quote(
        symbol=symbol.upper(),
        side=side,
        quantity=quantity,
        engine_type=EngineType.CLOB,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "side": side.value,
            "quantity": float(quantity),
            "estimated_avg_price": float(result.effective_price),
            "estimated_total": float(result.output_amount) if side == OrderSide.SELL else float(result.input_amount),
            "fee_amount": float(result.fee_amount),
            "fee_asset": result.fee_asset,
        },
    )


@router.post("/order", response_model=APIResponse)
async def place_order(
    request: PlaceOrderRequest,
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Place an order on the CLOB orderbook. Supports limit and market orders.
    """
    result = await router.execute_trade(
        user_id=user_id,
        symbol=symbol.upper(),
        side=request.side,
        quantity=request.quantity,
        price=request.price,
        order_type=request.order_type,
        engine_type=EngineType.CLOB,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    symbol_upper = symbol.upper()
    engine = await router._get_engine(symbol_upper, EngineType.CLOB)
    if engine:
        order_book = await engine._get_order_book(ORDERBOOK_WS_LEVELS)
        await ws_broadcast_orderbook(
            symbol_upper,
            {"bids": order_book["bids"], "asks": order_book["asks"]},
        )

    return APIResponse(
        success=True,
        data={
            "order_id": str(result.order_id) if result.order_id else None,
            "trade_id": str(result.trade_id) if result.trade_id else None,
            "symbol": symbol_upper,
            "side": result.side.value,
            "order_type": request.order_type.value,
            "price": float(request.price) if request.price else float(result.price),
            "quantity": float(request.quantity),
            "filled_quantity": float(result.quantity),
            "status": result.status.value,
            "fills": result.fills,
        },
    )


@router.post("/order/cancel", response_model=APIResponse)
async def cancel_order(
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    order_id: str = Query(..., description="Order ID to cancel"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Cancel an open order. Only works for orders that are still open or partially filled.
    """
    engine = await router._get_engine(symbol.upper(), EngineType.CLOB)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"CLOB market '{symbol}' not found")
    
    result = await engine.cancel_order(user_id, order_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to cancel order"))

    symbol_upper = symbol.upper()
    order_book = await engine._get_order_book(ORDERBOOK_WS_LEVELS)
    await ws_broadcast_orderbook(
        symbol_upper,
        {"bids": order_book["bids"], "asks": order_book["asks"]},
    )

    return APIResponse(success=True, data=result)


@router.get("/orders", response_model=APIResponse)
async def get_user_orders(
    symbol: str = Query(..., description="Symbol (e.g. AMM/USDT-USDT:SPOT)"),
    user_id: str = Depends(get_current_user_id),
    status: Optional[List[OrderStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get your orders for a specific CLOB market.
    """
    db = get_db()
    
    query = """
        SELECT o.*, sc.symbol FROM orderbook_orders o
        JOIN symbol_configs sc USING (symbol_id)
        WHERE o.user_id = $1 AND sc.symbol = $2 AND sc.engine_type = 1
    """
    params = [user_id, symbol.upper()]
    param_idx = 3
    
    if status:
        status_values = [s.value for s in status]
        query += f" AND o.status = ANY(${param_idx})"
        params.append(status_values)
        param_idx += 1
    
    query += f" ORDER BY o.created_at DESC LIMIT ${param_idx}"
    params.append(limit)
    
    orders = await db.read(query, *params)
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "orders": orders,
        },
    )


@router.get("/user/orders", response_model=APIResponse)
async def get_all_user_orders(
    user_id: str = Depends(get_current_user_id),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[List[OrderStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get all your orders across all CLOB markets.
    """
    db = get_db()
    
    query = """
        SELECT o.*, sc.symbol FROM orderbook_orders o
        JOIN symbol_configs sc USING (symbol_id)
        WHERE o.user_id = $1 AND sc.engine_type = 1
    """
    params = [user_id]
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
    
    orders = await db.read(query, *params)
    
    return APIResponse(success=True, data=orders)
