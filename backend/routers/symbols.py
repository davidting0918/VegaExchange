"""
Symbol Configuration API Routes
"""

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, SymbolStatus
from backend.models.requests import CreateSymbolRequest
from backend.models.responses import APIResponse, SymbolConfigResponse

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


def get_router() -> EngineRouter:
    """Dependency to get engine router"""
    return EngineRouter(get_db())


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

    # Create symbol config
    symbol_data = {
        "symbol": request.symbol,
        "base_asset": request.base_asset,
        "quote_asset": request.quote_asset,
        "engine_type": request.engine_type.value,
        "status": SymbolStatus.ACTIVE.value,
        "engine_params": request.engine_params,
        "min_trade_amount": request.min_trade_amount,
        "max_trade_amount": request.max_trade_amount,
        "price_precision": request.price_precision,
        "quantity_precision": request.quantity_precision,
    }

    result = await db.execute_returning(
        """
        INSERT INTO symbol_configs (
            symbol, base_asset, quote_asset, engine_type, status,
            engine_params, min_trade_amount, max_trade_amount,
            price_precision, quantity_precision
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        RETURNING *
        """,
        symbol_data["symbol"],
        symbol_data["base_asset"],
        symbol_data["quote_asset"],
        symbol_data["engine_type"],
        symbol_data["status"],
        symbol_data["engine_params"],
        symbol_data["min_trade_amount"],
        symbol_data["max_trade_amount"],
        symbol_data["price_precision"],
        symbol_data["quantity_precision"],
    )

    # Initialize engine-specific data
    if request.engine_type == EngineType.AMM:
        # Create AMM pool with initial reserves from params
        initial_base = request.engine_params.get("initial_reserve_base", 0)
        initial_quote = request.engine_params.get("initial_reserve_quote", 0)
        fee_rate = request.engine_params.get("fee_rate", 0.003)

        await db.execute(
            """
            INSERT INTO amm_pools (
                symbol_config_id, reserve_base, reserve_quote,
                k_value, fee_rate
            ) VALUES ($1, $2, $3, $4, $5)
            """,
            result["id"],
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

    result = await db.execute(
        """
        UPDATE symbol_configs
        SET status = $2, updated_at = NOW()
        WHERE symbol = $1
        """,
        symbol.upper(),
        status.value,
    )

    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    router.invalidate_cache(symbol.upper())

    return APIResponse(success=True, data={"symbol": symbol.upper(), "status": status.value})


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
        SET status = 'maintenance', updated_at = NOW()
        WHERE symbol = $1
        """,
        symbol.upper(),
    )

    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    router.invalidate_cache(symbol.upper())

    return APIResponse(success=True, data={"symbol": symbol.upper(), "deleted": True})
