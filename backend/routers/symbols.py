"""
Symbol Configuration API Routes
"""

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.core.id_generator import generate_pool_id, generate_symbol_id
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, SymbolStatus
from backend.models.requests import CreateSymbolRequest
from backend.models.responses import APIResponse, SymbolConfigResponse

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@router.get("", response_model=APIResponse)
async def list_symbols(router: EngineRouter = Depends(get_router)):
    """
    Get all active trading symbols.

    Returns list of symbols with their configurations.
    """
    symbols = await router.get_all_symbols()
    return APIResponse(success=True, data=symbols)


@router.get("/{symbol}", response_model=APIResponse)
async def get_symbol(symbol: str, router: EngineRouter = Depends(get_router)):
    """
    Get detailed information about a specific symbol.

    Includes configuration and current market data.
    """
    info = await router.get_symbol_info(symbol.upper())
    if not info:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    return APIResponse(success=True, data=info)


@router.post("", response_model=APIResponse)
async def create_symbol(request: CreateSymbolRequest, router: EngineRouter = Depends(get_router)):
    """
    Create a new trading symbol.

    Admin only - creates symbol configuration and initializes engine-specific data.
    """
    db = get_db()

    # Check if symbol already exists
    existing = await db.read_one(
        "SELECT id FROM symbol_configs WHERE symbol = $1",
        request.symbol,
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol '{request.symbol}' already exists")

    # Create symbol config (SERIAL id is auto-generated)
    result = await db.execute_returning(
        """
        INSERT INTO symbol_configs (
            symbol, market, base, quote, settle, engine_type, is_active,
            engine_params, min_trade_amount, max_trade_amount,
            price_precision, quantity_precision
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING *
        """,
        request.symbol,
        "spot",  # Default market type
        request.base_asset,
        request.quote_asset,
        request.quote_asset,  # Default settle to quote asset
        request.engine_type.value,
        True,  # is_active
        request.engine_params,
        request.min_trade_amount,
        request.max_trade_amount,
        request.price_precision,
        request.quantity_precision,
    )

    # Initialize engine-specific data
    if request.engine_type == EngineType.AMM:
        # Create AMM pool with initial reserves from params
        initial_base = request.engine_params.get("initial_reserve_base", 0)
        initial_quote = request.engine_params.get("initial_reserve_quote", 0)
        fee_rate = request.engine_params.get("fee_rate", 0.003)

        # Generate pool ID
        pool_id = generate_pool_id()
        
        await db.execute(
            """
            INSERT INTO amm_pools (
                pool_id, symbol_id, reserve_base, reserve_quote,
                k_value, fee_rate
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            pool_id,
            result["symbol_id"],
            initial_base,
            initial_quote,
            initial_base * initial_quote,
            fee_rate,
        )

    # Invalidate cache
    router.invalidate_cache(request.symbol)

    return APIResponse(success=True, data=result)


@router.put("/{symbol}/status", response_model=APIResponse)
async def update_symbol_status(
    symbol: str,
    status: SymbolStatus,
    router: EngineRouter = Depends(get_router),
):
    """
    Update symbol trading status.

    Can pause/resume trading for maintenance.
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


@router.delete("/{symbol}", response_model=APIResponse)
async def delete_symbol(symbol: str, router: EngineRouter = Depends(get_router)):
    """
    Delete a symbol (soft delete by setting status to maintenance).

    For safety, this doesn't actually delete the data.
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
