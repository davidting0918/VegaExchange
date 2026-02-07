"""
AMM Pool API Routes

All AMM-specific endpoints including swaps, liquidity, and pool data.
Endpoint prefix: /api/pool
"""

import re
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


@router.get("", response_model=APIResponse)
async def list_pools(router: EngineRouter = Depends(get_router)):
    """
    List all active AMM pools.
    
    Returns pool configurations and current market data.
    """
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


@router.get("/{symbol_path}", response_model=APIResponse)
async def get_pool(
    symbol_path: str,
    router: EngineRouter = Depends(get_router),
):
    """
    Get AMM pool data for a symbol.
    
    Path format: {base}-{quote}-{settle}-{market}
    Example: /api/pool/AMM-USDT-USDT-SPOT
    
    Returns reserve amounts, k value, fee rate, and trading statistics.
    """
    symbol = parse_symbol_path(symbol_path)
    components = parse_symbol_path_components(symbol_path)
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    pool = await engine._get_pool()
    
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol}'")
    
    data: dict = {
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
    }
    if components:
        base, quote, settle, market = components
        data["base"] = base
        data["quote"] = quote
        data["settle"] = settle
        data["market"] = market
    
    return APIResponse(success=True, data=data)


@router.get("/{symbol_path}/trades", response_model=APIResponse)
async def get_pool_trades(
    symbol_path: str,
    limit: int = Query(50, ge=1, le=200, description="Number of recent trades"),
):
    """
    Get recent AMM trades for a symbol.
    
    Path format: {base}-{quote}-{settle}-{market}
    Example: /api/pool/AMM-USDT-USDT-SPOT/trades
    """
    symbol = parse_symbol_path(symbol_path)
    components = parse_symbol_path_components(symbol_path)
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
    
    trades_data: dict = {
        "symbol": symbol,
        "trades": trades,
    }
    if components:
        base, quote, settle, market = components
        trades_data["base"] = base
        trades_data["quote"] = quote
        trades_data["settle"] = settle
        trades_data["market"] = market
    return APIResponse(success=True, data=trades_data)


@router.get("/{symbol_path}/quote", response_model=APIResponse)
async def get_swap_quote(
    symbol_path: str,
    side: OrderSide = Query(..., description="Buy or sell"),
    quantity: Optional[Decimal] = Query(None, description="Amount of base asset"),
    quote_amount: Optional[Decimal] = Query(None, description="Amount of quote asset"),
    router: EngineRouter = Depends(get_router),
):
    """
    Get a quote for an AMM swap.
    
    Path format: {base}-{quote}-{settle}-{market}
    Example: /api/pool/AMM-USDT-USDT-SPOT/quote
    
    Preview swap execution without actually trading.
    """
    symbol = parse_symbol_path(symbol_path)
    components = parse_symbol_path_components(symbol_path)
    result = await router.get_quote(
        symbol=symbol,
        side=side,
        quantity=quantity,
        quote_amount=quote_amount,
        engine_type=EngineType.AMM,
    )
    
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message)
    
    quote_data: dict = {
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
    }
    if components:
        base, quote, settle, market = components
        quote_data["base"] = base
        quote_data["quote"] = quote
        quote_data["settle"] = settle
        quote_data["market"] = market
    return APIResponse(success=True, data=quote_data)


@router.get("/{symbol_path}/liquidity/add/quote", response_model=APIResponse)
async def get_add_liquidity_quote(
    symbol_path: str,
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

    symbol = parse_symbol_path(symbol_path)
    components = parse_symbol_path_components(symbol_path)
    engine = await router._get_engine(symbol, EngineType.AMM)

    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")

    pool = await engine._get_pool()
    if not pool:
        raise HTTPException(status_code=404, detail=f"No pool data for '{symbol}'")

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
    return APIResponse(success=True, data=remove_data)


@router.get("/liquidity/position/{symbol_path}", response_model=APIResponse)
async def get_lp_position(
    symbol_path: str,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get your LP position for an AMM pool.
    
    Path format: {base}-{quote}-{settle}-{market}
    Example: /api/pool/liquidity/position/AMM-USDT-USDT-SPOT
    """
    symbol = parse_symbol_path(symbol_path)
    engine = await router._get_engine(symbol, EngineType.AMM)
    
    if not engine:
        raise HTTPException(status_code=404, detail=f"AMM pool '{symbol}' not found")
    
    position = await engine._get_lp_position(user_id)
    
    components = parse_symbol_path_components(symbol_path)
    if not position:
        pos_data: dict = {
            "symbol": symbol,
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
        "symbol": symbol,
        "lp_shares": float(position["lp_shares"]),
        "initial_base_amount": float(position["initial_base_amount"]),
        "initial_quote_amount": float(position["initial_quote_amount"]),
        "estimated_base_value": float(estimated_base_value),
        "estimated_quote_value": float(estimated_quote_value),
        "pool_share_percentage": float(share_ratio * 100),
        "has_position": True,
    }
    if components:
        base, quote, settle, market = components
        pos_data["base"] = base
        pos_data["quote"] = quote
        pos_data["settle"] = settle
        pos_data["market"] = market
    return APIResponse(success=True, data=pos_data)


@router.get("/liquidity/history/{symbol_path}", response_model=APIResponse)
async def get_liquidity_history(
    symbol_path: str,
    user_id: str = Depends(get_current_user_id),
    router: EngineRouter = Depends(get_router),
):
    """
    Get your liquidity event history for an AMM pool.
    
    Path format: {base}-{quote}-{settle}-{market}
    Example: /api/pool/liquidity/history/AMM-USDT-USDT-SPOT
    """
    symbol = parse_symbol_path(symbol_path)
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
    
    history_data: dict = {
        "symbol": symbol,
        "events": formatted_events,
    }
    components = parse_symbol_path_components(symbol_path)
    if components:
        base, quote, settle, market = components
        history_data["base"] = base
        history_data["quote"] = quote
        history_data["settle"] = settle
        history_data["market"] = market
    return APIResponse(success=True, data=history_data)
