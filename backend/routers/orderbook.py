"""
CLOB Orderbook API Routes — thin router, delegates to services/orderbook.py.
"""

from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from backend.core.auth import get_current_user_id
from backend.core.dependencies import get_router
from backend.engines.engine_router import EngineRouter
from backend.models.common import APIResponse
from backend.models.enums import OrderSide, OrderStatus
from backend.models.requests import PlaceOrderRequest
from backend.services import orderbook as orderbook_service

router = APIRouter(prefix="/api/orderbook", tags=["clob-orderbook"])


@router.get("", response_model=APIResponse)
async def list_orderbook_markets(
    symbol: Optional[str] = Query(None, description="Symbol. When provided, returns single orderbook."),
    levels: int = Query(20, ge=1, le=100, description="Number of price levels"),
    router: EngineRouter = Depends(get_router),
):
    """List all active CLOB markets, or get a single orderbook."""
    data = await orderbook_service.get_orderbook_markets(router, symbol, levels)
    return APIResponse(success=True, data=data)


@router.get("/trades", response_model=APIResponse)
async def get_orderbook_trades(
    symbol: str = Query(..., description="Symbol"),
    limit: int = Query(100, ge=1, le=200, description="Number of recent trades"),
):
    """Get recent CLOB trades for a symbol."""
    data = await orderbook_service.get_trades(symbol, limit)
    return APIResponse(success=True, data=data)


@router.get("/quote", response_model=APIResponse)
async def get_order_quote(
    symbol: str = Query(..., description="Symbol"),
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Decimal = Query(..., description="Amount of base asset"),
    router: EngineRouter = Depends(get_router),
):
    """Get a quote for a market order. Preview without execution."""
    data = await orderbook_service.get_quote(router, symbol, side, quantity)
    return APIResponse(success=True, data=data)


@router.post("/order", response_model=APIResponse)
async def place_order(
    request: PlaceOrderRequest,
    symbol: str = Query(..., description="Symbol"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Place an order on the CLOB orderbook."""
    data = await orderbook_service.place_order(
        router, user_id, symbol,
        side=request.side, order_type=request.order_type,
        quantity=request.quantity, price=request.price,
    )
    return APIResponse(success=True, data=data)


@router.post("/order/cancel", response_model=APIResponse)
async def cancel_order(
    symbol: str = Query(..., description="Symbol"),
    order_id: str = Query(..., description="Order ID to cancel"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Cancel an open order."""
    data = await orderbook_service.cancel_order(router, user_id, symbol, order_id)
    return APIResponse(success=True, data=data)


@router.get("/orders", response_model=APIResponse)
async def get_user_orders(
    symbol: str = Query(..., description="Symbol"),
    user_id: str = Depends(get_current_user_id),
    status: Optional[List[OrderStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Get your orders for a specific CLOB market."""
    data = await orderbook_service.get_user_orders(user_id, symbol, status, limit)
    return APIResponse(success=True, data=data)


@router.get("/user/orders", response_model=APIResponse)
async def get_all_user_orders(
    user_id: str = Depends(get_current_user_id),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[List[OrderStatus]] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Get all your orders across all CLOB markets."""
    data = await orderbook_service.get_all_user_orders(user_id, symbol, status, limit)
    return APIResponse(success=True, data=data)
