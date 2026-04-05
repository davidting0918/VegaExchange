"""
Admin API Routes

All endpoints require admin permissions.
"""

import json
from decimal import Decimal
from math import sqrt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.audit_log import AuditContext, audit_logged, get_audit_context
from backend.core.auth import require_admin
from backend.core.dependencies import get_router
from backend.core.db_manager import get_db
from backend.core.id_generator import generate_pool_id
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, SymbolStatus
from backend.models.requests import CreatePoolRequest, CreateSymbolRequest
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# Symbol Management
# =============================================================================

@router.post("/create_symbol", response_model=APIResponse)
@audit_logged(action="create_symbol", target_type="symbol")
async def create_symbol(
    request: CreateSymbolRequest,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
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
            detail="Only CLOB symbols can be created manually. Use /create_pool endpoint for AMM symbols."
        )

    # Check if symbol + engine_type combination already exists
    existing = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = $2",
        request.symbol,
        request.engine_type.value,
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{request.symbol}' with engine_type CLOB already exists"
        )

    settle_asset = request.settle if request.settle else request.quote_asset
    engine_params_json = json.dumps(request.engine_params) if request.engine_params else "{}"

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
        True,
        engine_params_json,
        request.min_trade_amount,
        request.max_trade_amount,
        request.price_precision,
        request.quantity_precision,
    )

    router.invalidate_cache(request.symbol)

    audit.set(
        target_id=str(result["symbol_id"]),
        details={"symbol": request.symbol, "engine_type": request.engine_type.value},
    )

    return APIResponse(success=True, data=result)


@router.post("/create_pool", response_model=APIResponse)
@audit_logged(action="create_pool", target_type="pool")
async def create_pool(
    request: CreatePoolRequest,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """
    Create a new AMM pool (auto-creates symbol).

    Creates both the symbol configuration (AMM engine) and the AMM pool
    with initial reserves in one operation.
    Requires admin permissions.
    """
    db = get_db()

    existing = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = $2",
        request.symbol,
        EngineType.AMM.value,
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{request.symbol}' with engine_type AMM already exists"
        )

    settle_asset = request.settle if request.settle else request.quote_asset

    engine_params = {
        "initial_reserve_base": float(request.initial_reserve_base),
        "initial_reserve_quote": float(request.initial_reserve_quote),
        "fee_rate": float(request.fee_rate),
    }
    engine_params_json = json.dumps(engine_params)

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
        EngineType.AMM.value,
        True,
        engine_params_json,
        request.min_trade_amount,
        request.max_trade_amount,
        request.price_precision,
        request.quantity_precision,
    )

    pool_id = generate_pool_id()
    k_value = request.initial_reserve_base * request.initial_reserve_quote
    protocol_lp_shares = Decimal(str(sqrt(float(request.initial_reserve_base * request.initial_reserve_quote))))

    pool_result = await db.execute_returning(
        """
        INSERT INTO amm_pools (
            pool_id, symbol_id, reserve_base, reserve_quote,
            k_value, fee_rate, total_lp_shares
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING *
        """,
        pool_id,
        symbol_result["symbol_id"],
        request.initial_reserve_base,
        request.initial_reserve_quote,
        k_value,
        request.fee_rate,
        protocol_lp_shares,
    )

    router.invalidate_cache(request.symbol)

    audit.set(
        target_id=pool_id,
        details={
            "symbol": request.symbol,
            "symbol_id": symbol_result["symbol_id"],
            "fee_rate": float(request.fee_rate),
        },
    )

    return APIResponse(
        success=True,
        data={
            "symbol": symbol_result,
            "pool": pool_result,
            "protocol_lp_shares": float(protocol_lp_shares),
        },
    )


@router.post("/update_symbol_status/{symbol}", response_model=APIResponse)
@audit_logged(action="update_symbol_status", target_type="symbol")
async def update_symbol_status(
    symbol: str,
    status: SymbolStatus = Query(..., description="Symbol status (ACTIVE or MAINTENANCE)"),
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """
    Update symbol trading status.

    Can pause/resume trading for maintenance.
    Requires admin permissions.
    """
    db = get_db()

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

    audit.set(
        target_id=symbol.upper(),
        details={"new_status": "active" if is_active else "maintenance"},
    )

    return APIResponse(success=True, data={"symbol": symbol.upper(), "is_active": is_active})


@router.post("/delete_symbol/{symbol}", response_model=APIResponse)
@audit_logged(action="delete_symbol", target_type="symbol")
async def delete_symbol(
    symbol: str,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
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

    audit.set(target_id=symbol.upper())

    return APIResponse(success=True, data={"symbol": symbol.upper(), "deleted": True})


# =============================================================================
# Audit Log Viewer
# =============================================================================

@router.get("/audit-log", response_model=APIResponse)
async def get_audit_log(
    admin_id: Optional[str] = Query(None, description="Filter by admin ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    date_from: Optional[str] = Query(None, description="Start date (ISO format)"),
    date_to: Optional[str] = Query(None, description="End date (ISO format)"),
    limit: int = Query(50, ge=1, le=200, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
    current_admin: dict = Depends(require_admin),
):
    """
    Query admin audit log with pagination and filters.

    Returns log entries joined with admin name/email from the admins table.
    """
    db = get_db()

    # Build dynamic WHERE clause
    conditions = []
    params = []
    param_idx = 1

    if admin_id:
        conditions.append(f"aal.admin_id = ${param_idx}")
        params.append(admin_id)
        param_idx += 1

    if action:
        conditions.append(f"aal.action = ${param_idx}")
        params.append(action)
        param_idx += 1

    if target_type:
        conditions.append(f"aal.target_type = ${param_idx}")
        params.append(target_type)
        param_idx += 1

    if date_from:
        conditions.append(f"aal.created_at >= ${param_idx}::timestamptz")
        params.append(date_from)
        param_idx += 1

    if date_to:
        conditions.append(f"aal.created_at <= ${param_idx}::timestamptz")
        params.append(date_to)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    # Count total
    total = await db.read_one(
        f"SELECT COUNT(*) as count FROM admin_audit_logs aal WHERE {where_clause}",
        *params,
    )

    # Fetch page with admin info
    logs = await db.read(
        f"""
        SELECT
            aal.id,
            aal.admin_id,
            a.name as admin_name,
            a.email as admin_email,
            aal.action,
            aal.target_type,
            aal.target_id,
            aal.details,
            aal.created_at
        FROM admin_audit_logs aal
        JOIN admins a ON aal.admin_id = a.admin_id
        WHERE {where_clause}
        ORDER BY aal.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params,
        limit,
        offset,
    )

    return APIResponse(
        success=True,
        data={
            "logs": logs,
            "total": total["count"] if total else 0,
            "limit": limit,
            "offset": offset,
        },
    )
