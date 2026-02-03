"""
Admin API Routes

All endpoints require admin permissions.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import require_admin
from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.core.id_generator import generate_pool_id
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, SymbolStatus
from backend.models.requests import CreatePoolRequest, CreateSymbolRequest
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/create_symbol", response_model=APIResponse)
async def create_symbol(
    request: CreateSymbolRequest,
    router: EngineRouter = Depends(get_router),
    current_user: dict = Depends(require_admin),
):
    """
    Create a new trading symbol (CLOB only).

    Creates symbol configuration for CLOB engine type.
    AMM symbols should be created via /create_pool endpoint.
    Requires admin permissions.
    """
    db = get_db()

    # Only allow CLOB engine type for manual symbol creation
    if request.engine_type != EngineType.CLOB:
        raise HTTPException(
            status_code=400,
            detail=f"Only CLOB symbols can be created manually. Use /create_pool endpoint for AMM symbols."
        )

    # Check if symbol already exists
    existing = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1",
        request.symbol,
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol '{request.symbol}' already exists")

    # Ensure settle is set (defaults to quote_asset)
    settle_asset = request.settle if request.settle else request.quote_asset
    
    # Convert engine_params dict to JSON string for JSONB column
    engine_params_json = json.dumps(request.engine_params) if request.engine_params else "{}"
    
    # Create symbol config (SERIAL id is auto-generated)
    result = await db.execute_returning(
        """
        INSERT INTO symbol_configs (
            symbol, market, base, quote, settle, engine_type, is_active,
            engine_params, min_trade_amount, max_trade_amount,
            price_precision, quantity_precision
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12)
        RETURNING *
        """,
        request.symbol,
        request.market.upper() if request.market else "SPOT",
        request.base_asset,
        request.quote_asset,
        settle_asset,
        request.engine_type.value,
        True,  # is_active
        engine_params_json,
        request.min_trade_amount,
        request.max_trade_amount,
        request.price_precision,
        request.quantity_precision,
    )

    # Invalidate cache
    router.invalidate_cache(request.symbol)

    return APIResponse(success=True, data=result)


@router.post("/create_pool", response_model=APIResponse)
async def create_pool(
    request: CreatePoolRequest,
    router: EngineRouter = Depends(get_router),
    current_user: dict = Depends(require_admin),
):
    """
    Create a new AMM pool (auto-creates symbol).

    Creates both the symbol configuration (AMM engine) and the AMM pool
    with initial reserves in one operation.
    Requires admin permissions.
    """
    db = get_db()

    # Check if symbol already exists
    existing = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1",
        request.symbol,
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol '{request.symbol}' already exists")

    # Ensure settle is set (defaults to quote_asset)
    settle_asset = request.settle if request.settle else request.quote_asset
    
    # Build engine_params from pool parameters
    engine_params = {
        "initial_reserve_base": float(request.initial_reserve_base),
        "initial_reserve_quote": float(request.initial_reserve_quote),
        "fee_rate": float(request.fee_rate),
    }
    engine_params_json = json.dumps(engine_params)
    
    # Create symbol config with AMM engine type (SERIAL id is auto-generated)
    symbol_result = await db.execute_returning(
        """
        INSERT INTO symbol_configs (
            symbol, market, base, quote, settle, engine_type, is_active,
            engine_params, min_trade_amount, max_trade_amount,
            price_precision, quantity_precision
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12)
        RETURNING *
        """,
        request.symbol,
        request.market.upper() if request.market else "SPOT",
        request.base_asset,
        request.quote_asset,
        settle_asset,
        EngineType.AMM.value,  # Always AMM for pools
        True,  # is_active
        engine_params_json,
        request.min_trade_amount,
        request.max_trade_amount,
        request.price_precision,
        request.quantity_precision,
    )

    # Generate pool ID
    pool_id = generate_pool_id()
    
    # Calculate initial k_value
    k_value = request.initial_reserve_base * request.initial_reserve_quote
    
    # Create AMM pool
    pool_result = await db.execute_returning(
        """
        INSERT INTO amm_pools (
            pool_id, symbol_id, reserve_base, reserve_quote,
            k_value, fee_rate
        ) VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        pool_id,
        symbol_result["symbol_id"],
        request.initial_reserve_base,
        request.initial_reserve_quote,
        k_value,
        request.fee_rate,
    )

    # Invalidate cache
    router.invalidate_cache(request.symbol)

    return APIResponse(
        success=True,
        data={
            "symbol": symbol_result,
            "pool": pool_result,
        },
    )


@router.post("/update_symbol_status/{symbol}", response_model=APIResponse)
async def update_symbol_status(
    symbol: str,
    status: SymbolStatus = Query(..., description="Symbol status (ACTIVE or MAINTENANCE)"),
    router: EngineRouter = Depends(get_router),
    current_user: dict = Depends(require_admin),
):
    """
    Update symbol trading status.

    Can pause/resume trading for maintenance.
    Requires admin permissions.
    """
    db = get_db()

    # Convert SymbolStatus to boolean
    is_active = status == SymbolStatus.ACTIVE
    
    result = await db.execute(
        """
        UPDATE symbol_configs
        SET is_active = $2, updated_at = NOW()
        WHERE symbol = $1
        """,
        symbol.upper(),
        is_active,
    )

    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    router.invalidate_cache(symbol.upper())

    return APIResponse(success=True, data={"symbol": symbol.upper(), "is_active": is_active})


@router.post("/delete_symbol/{symbol}", response_model=APIResponse)
async def delete_symbol(
    symbol: str,
    router: EngineRouter = Depends(get_router),
    current_user: dict = Depends(require_admin),
):
    """
    Delete a symbol (soft delete by setting status to maintenance).

    For safety, this doesn't actually delete the data.
    Requires admin permissions.
    """
    db = get_db()

    result = await db.execute(
        """
        UPDATE symbol_configs
        SET is_active = FALSE, updated_at = NOW()
        WHERE symbol = $1
        """,
        symbol.upper(),
    )

    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    router.invalidate_cache(symbol.upper())

    return APIResponse(success=True, data={"symbol": symbol.upper(), "deleted": True})
