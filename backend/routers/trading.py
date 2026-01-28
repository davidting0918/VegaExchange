"""
Trading API Routes

Unified trading endpoint that routes to the appropriate engine.
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import get_current_user_id
from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType
from backend.models.requests import AddLiquidityRequest, PlaceOrderRequest, RemoveLiquidityRequest, SwapRequest, TradeRequest
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/trade", tags=["trading"])


@router.post("", response_model=APIResponse)
async def execute_trade(
    request: TradeRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Execute a trade on any symbol.

    This is the unified trade endpoint that works for all engine types.
    The router automatically detects the engine type and routes appropriately.

    For AMM:
        - BUY: Specify quote_amount (USDT to spend)
        - SELL: Specify quantity (base asset to sell)

    For CLOB:
        - Specify quantity, order_type, and price (for limit orders)
    """
    result = await router.execute_trade(
        user_id=user_id,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        quote_amount=request.quote_amount,
        price=request.price,
        order_type=request.order_type,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    return APIResponse(
        success=True,
        data={
            "trade_id": str(result.trade_id) if result.trade_id else None,
            "order_id": str(result.order_id) if result.order_id else None,
            "symbol": result.symbol,
            "side": result.side.value,
            "engine_type": result.engine_type.value,
            "price": float(result.price),
            "quantity": float(result.quantity),
            "quote_amount": float(result.quote_amount),
            "fee_amount": float(result.fee_amount),
            "fee_asset": result.fee_asset,
            "status": result.status.value,
            "fills": result.fills,
            "engine_data": result.engine_data,
        },
    )


@router.post("/swap", response_model=APIResponse)
async def execute_swap(
    request: SwapRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Execute an AMM swap.

    Specifically for AMM pools with slippage protection.
    """
    # Determine quantity vs quote_amount based on side
    if request.side == OrderSide.BUY:
        quantity = None
        quote_amount = request.amount_in
    else:
        quantity = request.amount_in
        quote_amount = None

    result = await router.execute_trade(
        user_id=user_id,
        symbol=request.symbol,
        side=request.side,
        quantity=quantity,
        quote_amount=quote_amount,
        min_amount_out=request.min_amount_out,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    return APIResponse(
        success=True,
        data={
            "trade_id": str(result.trade_id) if result.trade_id else None,
            "symbol": result.symbol,
            "side": result.side.value,
            "price": float(result.price),
            "quantity": float(result.quantity),
            "quote_amount": float(result.quote_amount),
            "fee_amount": float(result.fee_amount),
            "price_impact": result.engine_data.get("price_impact"),
        },
    )


@router.post("/order", response_model=APIResponse)
async def place_order(
    request: PlaceOrderRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Place an order on a CLOB symbol.

    Supports limit and market orders.
    """
    result = await router.execute_trade(
        user_id=user_id,
        symbol=request.symbol,
        side=request.side,
        quantity=request.quantity,
        price=request.price,
        order_type=request.order_type,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    return APIResponse(
        success=True,
        data={
            "order_id": str(result.order_id) if result.order_id else None,
            "trade_id": str(result.trade_id) if result.trade_id else None,
            "symbol": result.symbol,
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
    order_id: str = Query(..., description="Order ID to cancel"),
    symbol: str = Query(..., description="Symbol of the order"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Cancel an open order.

    Only works for CLOB orders that are still open or partially filled.
    """
    engine = await router._get_engine(symbol)

    if not engine:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if engine.engine_type != EngineType.CLOB:
        raise HTTPException(status_code=400, detail="Cancel only works for CLOB orders")

    result = await engine.cancel_order(user_id, order_id)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to cancel order"))

    return APIResponse(success=True, data=result)


@router.get("/quote", response_model=APIResponse)
async def get_quote(
    symbol: str = Query(..., description="Trading symbol"),
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Optional[Decimal] = Query(None, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get a quote for a potential trade.

    Preview trade execution without actually trading.
    """
    result = await router.get_quote(
        symbol=symbol,
        side=side,
        quantity=quantity,
        quote_amount=quote_amount,
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "side": side.value,
            "input_amount": float(result.input_amount),
            "input_asset": result.input_asset,
            "output_amount": float(result.output_amount),
            "output_asset": result.output_asset,
            "effective_price": float(result.effective_price),
            "price_impact": float(result.price_impact) if result.price_impact else None,
            "fee_amount": float(result.fee_amount),
            "fee_asset": result.fee_asset,
            "slippage": float(result.slippage) if result.slippage else None,
        },
    )


@router.get("/orders", response_model=APIResponse)
async def get_user_orders(
    user_id: str = Depends(get_current_user_id),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[List[OrderStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get user's orders.

    Can filter by symbol and status.
    """
    db = get_db()

    query = """
        SELECT o.*, sc.symbol FROM orderbook_orders o
        JOIN symbol_configs sc USING (symbol_id)
        WHERE o.user_id = $1
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


@router.get("/history", response_model=APIResponse)
async def get_trade_history(
    user_id: str = Depends(get_current_user_id),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    engine_type: Optional[EngineType] = Query(None, description="Filter by engine type"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get user's trade history.

    Unified history across all engine types.
    """
    db = get_db()

    query = """
        SELECT t.*, sc.symbol FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE t.user_id = $1
    """
    params = [user_id]
    param_idx = 2

    if symbol:
        query += f" AND sc.symbol = ${param_idx}"
        params.append(symbol.upper())
        param_idx += 1

    if engine_type:
        query += f" AND t.engine_type = ${param_idx}"
        params.append(engine_type.value)
        param_idx += 1

    query += f" ORDER BY t.created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    trades = await db.read(query, *params)

    return APIResponse(success=True, data=trades)


@router.post("/liquidity/add", response_model=APIResponse)
async def add_liquidity(
    request: AddLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Add liquidity to an AMM pool.

    User provides both base and quote assets in the correct ratio.
    Returns LP shares representing the user's share of the pool.
    """
    engine = await router._get_engine(request.symbol)

    if not engine:
        raise HTTPException(status_code=404, detail=f"Symbol '{request.symbol}' not found")

    if engine.engine_type != EngineType.AMM:
        raise HTTPException(status_code=400, detail="Add liquidity only works for AMM symbols")

    result = await engine.add_liquidity(
        user_id=user_id,
        base_amount=request.base_amount,
        quote_amount=request.quote_amount,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to add liquidity"))

    return APIResponse(
        success=True,
        data={
            "symbol": request.symbol.upper(),
            "lp_shares": result["lp_shares"],
            "pool_id": result["pool_id"],
            "reserve_base": result["reserve_base"],
            "reserve_quote": result["reserve_quote"],
            "total_lp_shares": result["total_lp_shares"],
        },
    )


@router.post("/liquidity/remove", response_model=APIResponse)
async def remove_liquidity(
    request: RemoveLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Remove liquidity from an AMM pool.

    User burns LP shares and receives back base and quote assets
    proportional to their share of the pool.
    """
    engine = await router._get_engine(request.symbol)

    if not engine:
        raise HTTPException(status_code=404, detail=f"Symbol '{request.symbol}' not found")

    if engine.engine_type != EngineType.AMM:
        raise HTTPException(status_code=400, detail="Remove liquidity only works for AMM symbols")

    result = await engine.remove_liquidity(
        user_id=user_id,
        lp_shares=request.lp_shares,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove liquidity"))

    return APIResponse(
        success=True,
        data={
            "symbol": request.symbol.upper(),
            "base_out": result["base_out"],
            "quote_out": result["quote_out"],
            "lp_shares_burned": result["lp_shares_burned"],
            "remaining_lp_shares": result["remaining_lp_shares"],
            "pool_id": result["pool_id"],
            "reserve_base": result["reserve_base"],
            "reserve_quote": result["reserve_quote"],
            "total_lp_shares": result["total_lp_shares"],
        },
    )


@router.get("/liquidity/position", response_model=APIResponse)
async def get_lp_position(
    symbol: str = Query(..., description="Trading symbol"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get user's LP position for an AMM pool.
    """
    engine = await router._get_engine(symbol)

    if not engine:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if engine.engine_type != EngineType.AMM:
        raise HTTPException(status_code=400, detail="LP positions only available for AMM symbols")

    position = await engine._get_lp_position(user_id)

    if not position:
        return APIResponse(
            success=True,
            data={
                "symbol": symbol.upper(),
                "lp_shares": 0,
                "has_position": False,
            },
        )

    # Get current pool info to calculate user's share
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

    return APIResponse(
        success=True,
        data={
            "symbol": symbol.upper(),
            "lp_shares": float(position["lp_shares"]),
            "initial_base_amount": float(position["initial_base_amount"]),
            "initial_quote_amount": float(position["initial_quote_amount"]),
            "estimated_base_value": float(estimated_base_value),
            "estimated_quote_value": float(estimated_quote_value),
            "pool_share_percentage": float(share_ratio * 100),
            "has_position": True,
        },
    )
