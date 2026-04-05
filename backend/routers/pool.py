"""
AMM Pool API Routes — thin router, delegates to services/pool.py.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.core.auth import get_current_user_id
from backend.core.dependencies import get_router
from backend.engines.engine_router import EngineRouter
from backend.models.common import APIResponse
from backend.models.enums import OrderSide
from backend.models.pool import PeriodKind
from backend.models.requests import AddLiquidityRequest, RemoveLiquidityRequest, SwapRequest
from backend.services import pool as pool_service

router = APIRouter(prefix="/api/pool", tags=["amm-pool"])


@router.get("", response_model=APIResponse)
async def list_pools(
    symbol: Optional[str] = Query(None, description="Symbol in format base-quote-settle-market"),
    router: EngineRouter = Depends(get_router),
):
    """List all active AMM pools, or get a single pool."""
    data = await pool_service.list_pools(router, symbol)
    return APIResponse(success=True, data=data)


@router.get("/trades", response_model=APIResponse)
async def get_pool_trades(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    limit: int = Query(100, ge=1, le=200, description="Number of recent trades"),
):
    """Get recent AMM trades for a symbol."""
    data = await pool_service.get_pool_trades(symbol, limit)
    return APIResponse(success=True, data=data)


@router.get("/public", response_model=APIResponse)
async def get_pool_public(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    limit: int = Query(100, ge=1, le=200, description="Number of recent trades"),
    engine_router: EngineRouter = Depends(get_router),
):
    """Get public pool data + recent trades in one call."""
    data = await pool_service.get_pool_public(engine_router, symbol, limit)
    return APIResponse(success=True, data=data)


@router.get("/user", response_model=APIResponse)
async def get_pool_user(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Get user-specific pool data: LP position + base/quote balances."""
    data = await pool_service.get_pool_user(router, user_id, symbol)
    return APIResponse(success=True, data=data)


@router.get("/chart/volume", response_model=APIResponse)
async def get_pool_volume_chart(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    period: PeriodKind = Query("1D", description="Time range: 1H, 1D, 1W, 1M, 1Y, ALL"),
    limit: int = Query(100, ge=1, le=500, description="Max number of buckets"),
):
    """Get time-bucketed volume for a pool."""
    data = await pool_service.get_volume_chart(symbol, period, limit)
    return APIResponse(success=True, data=data)


@router.get("/chart/price-history", response_model=APIResponse)
async def get_pool_price_history(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    period: PeriodKind = Query("1D", description="Time range: 1H, 1D, 1W, 1M, 1Y, ALL"),
    limit: int = Query(500, ge=1, le=2000, description="Max number of points"),
):
    """Get price history for a pool."""
    data = await pool_service.get_price_history(symbol, period, limit)
    return APIResponse(success=True, data=data)


@router.get("/quote", response_model=APIResponse)
async def get_swap_quote(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Optional[Decimal] = Query(None, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """Get a quote for an AMM swap."""
    data = await pool_service.get_swap_quote(router, symbol, side, quantity, quote_amount)
    return APIResponse(success=True, data=data)


@router.get("/liquidity/add/quote", response_model=APIResponse)
async def get_add_liquidity_quote(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    base_amount: Optional[Decimal] = Query(None, gt=0, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, gt=0, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """Get quote for adding liquidity."""
    data = await pool_service.get_add_liquidity_quote(router, symbol, base_amount, quote_amount)
    return APIResponse(success=True, data=data)


@router.post("/swap", response_model=APIResponse)
async def execute_swap(
    request: SwapRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Execute an AMM swap."""
    data = await pool_service.execute_swap(
        router, user_id, request.symbol,
        side=request.side, amount_in=request.amount_in,
        min_amount_out=request.min_amount_out,
    )
    return APIResponse(success=True, data=data)


@router.post("/liquidity/add", response_model=APIResponse)
async def add_liquidity(
    request: AddLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Add liquidity to an AMM pool."""
    data = await pool_service.add_liquidity(
        router, user_id, request.symbol,
        base_amount=request.base_amount, quote_amount=request.quote_amount,
    )
    return APIResponse(success=True, data=data)


@router.post("/liquidity/remove", response_model=APIResponse)
async def remove_liquidity(
    request: RemoveLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Remove liquidity from an AMM pool."""
    data = await pool_service.remove_liquidity(
        router, user_id, request.symbol, lp_shares=request.lp_shares,
    )
    return APIResponse(success=True, data=data)


@router.get("/liquidity/position", response_model=APIResponse)
async def get_lp_position(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Get your LP position for an AMM pool."""
    data = await pool_service.get_lp_position(router, user_id, symbol)
    return APIResponse(success=True, data=data)


@router.get("/liquidity/history", response_model=APIResponse)
async def get_liquidity_history(
    symbol: str = Query(..., description="Symbol in format base-quote-settle-market"),
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """Get your liquidity event history for an AMM pool."""
    data = await pool_service.get_lp_history(router, user_id, symbol)
    return APIResponse(success=True, data=data)
