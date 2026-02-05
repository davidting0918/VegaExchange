"""
AMM Pool API Routes

All AMM-specific endpoints including swaps, liquidity, and pool data.
Endpoint prefix: /api/pool
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import get_current_user_id
from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, OrderSide
from backend.models.requests import AddLiquidityRequest, RemoveLiquidityRequest, SwapRequest
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/pool", tags=["amm-pool"])


def build_symbol(base: str, quote: str, settle: str, market: str) -> str:
    """
    Build symbol string from path components.
    
    Format: {BASE}/{QUOTE}-{SETTLE}:{MARKET}
    Example: AMM/USDT-USDT:SPOT
    """
    return f"{base.upper()}/{quote.upper()}-{settle.upper()}:{market.upper()}"


@router.get("", response_model=APIResponse)
async def list_pools(router: EngineRouter = Depends(get_router)):
    """
    List all active AMM pools.
    
    Returns pool configurations and current market data.
    """
    db = get_db()
    
    pools = await db.read(
        """
        SELECT sc.*, ap.reserve_base, ap.reserve_quote, ap.k_value, 
               ap.fee_rate, ap.total_lp_shares,
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


@router.get("/{base}/{quote}/{settle}/{market}", response_model=APIResponse)
async def get_pool(
    base: str,
    quote: str,
    settle: str,
    market: str,
    router: EngineRouter = Depends(get_router),
):
    """
    Get AMM pool data for a symbol.
    
    Returns reserve amounts, k value, fee rate, and trading statistics.
    """
    symbol = build_symbol(base, quote, settle, market)
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    pool = await engine._get_pool()
    
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol}'")
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol,
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
        },
    )


@router.get("/{base}/{quote}/{settle}/{market}/trades", response_model=APIResponse)
async def get_pool_trades(
    base: str,
    quote: str,
    settle: str,
    market: str,
    limit: int = Query(50, ge=1, le=200, description="Number of recent trades"),
):
    """
    Get recent AMM trades for a symbol.
    """
    symbol = build_symbol(base, quote, settle, market)
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
        symbol,
        limit,
    )
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol,
            "trades": trades,
        },
    )


@router.get("/{base}/{quote}/{settle}/{market}/quote", response_model=APIResponse)
async def get_swap_quote(
    base: str,
    quote: str,
    settle: str,
    market: str,
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Optional[Decimal] = Query(None, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get a quote for an AMM swap.
    
    Preview swap execution without actually trading.
    """
    symbol = build_symbol(base, quote, settle, market)
    result = await router.get_quote(
        symbol=symbol,
        side=side,
        quantity=quantity,
        quote_amount=quote_amount,
        engine_type=EngineType.AMM,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol,
            "side": side.value,
            "input_amount": float(result.input_amount),
            "input_asset": result.input_asset,
            "output_amount": float(result.output_amount),
            "output_asset": result.output_asset,
            "effective_price": float(result.effective_price),
            "price_impact": float(result.price_impact) if result.price_impact else None,
            "fee_amount": float(result.fee_amount),
            "fee_asset": result.fee_asset,
        },
    )


@router.post("/{base}/{quote}/{settle}/{market}/swap", response_model=APIResponse)
async def execute_swap(
    base: str,
    quote: str,
    settle: str,
    market: str,
    request: SwapRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Execute an AMM swap.
    
    - BUY: Spend quote asset (e.g., USDT) to get base asset
    - SELL: Sell base asset to get quote asset
    """
    # Override symbol from path
    symbol = build_symbol(base, quote, settle, market)
    request.symbol = symbol
    
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
        engine_type=EngineType.AMM,
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


@router.post("/{base}/{quote}/{settle}/{market}/liquidity/add", response_model=APIResponse)
async def add_liquidity(
    base: str,
    quote: str,
    settle: str,
    market: str,
    request: AddLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Add liquidity to an AMM pool.
    
    Provide both base and quote assets in the correct ratio.
    Returns LP shares representing your share of the pool.
    """
    symbol = build_symbol(base, quote, settle, market)
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
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol,
            "lp_shares": result["lp_shares"],
            "pool_id": result["pool_id"],
            "reserve_base": result["reserve_base"],
            "reserve_quote": result["reserve_quote"],
            "total_lp_shares": result["total_lp_shares"],
        },
    )


@router.post("/{base}/{quote}/{settle}/{market}/liquidity/remove", response_model=APIResponse)
async def remove_liquidity(
    base: str,
    quote: str,
    settle: str,
    market: str,
    request: RemoveLiquidityRequest,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Remove liquidity from an AMM pool.
    
    Burn LP shares and receive back base and quote assets
    proportional to your share of the pool.
    """
    symbol = build_symbol(base, quote, settle, market)
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    result = await engine.remove_liquidity(
        user_id=user_id,
        lp_shares=request.lp_shares,
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to remove liquidity"))
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol,
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


@router.get("/{base}/{quote}/{settle}/{market}/liquidity/position", response_model=APIResponse)
async def get_lp_position(
    base: str,
    quote: str,
    settle: str,
    market: str,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get your LP position for an AMM pool.
    """
    symbol = build_symbol(base, quote, settle, market)
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    position = await engine._get_lp_position(user_id)
    
    if not position:
        return APIResponse(
            success=True,
            data={
                "symbol": symbol,
                "lp_shares": 0,
                "has_position": False,
            },
        )
    
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
            "symbol": symbol,
            "lp_shares": float(position["lp_shares"]),
            "initial_base_amount": float(position["initial_base_amount"]),
            "initial_quote_amount": float(position["initial_quote_amount"]),
            "estimated_base_value": float(estimated_base_value),
            "estimated_quote_value": float(estimated_quote_value),
            "pool_share_percentage": float(share_ratio * 100),
            "has_position": True,
        },
    )


@router.get("/{base}/{quote}/{settle}/{market}/liquidity/history", response_model=APIResponse)
async def get_liquidity_history(
    base: str,
    quote: str,
    settle: str,
    market: str,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get your liquidity event history for an AMM pool.
    """
    symbol = build_symbol(base, quote, settle, market)
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol}'")
    
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
    
    return APIResponse(
        success=True,
        data={
            "symbol": symbol,
            "events": formatted_events,
        },
    )
