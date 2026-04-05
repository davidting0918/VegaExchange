"""
Admin domain service — symbol CRUD, pool admin, audit log queries.
"""

import json
from decimal import Decimal
from math import sqrt
from typing import Optional

from fastapi import HTTPException

from backend.core.db_manager import get_db
from backend.core.id_generator import generate_pool_id
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, SymbolStatus
from backend.models.requests import CreatePoolRequest, CreateSymbolRequest


async def create_symbol(request: CreateSymbolRequest, router: EngineRouter) -> dict:
    """Create a new CLOB trading symbol."""
    db = get_db()

    if request.engine_type != EngineType.CLOB:
        raise HTTPException(
            status_code=400,
            detail="Only CLOB symbols can be created manually. Use /create_pool endpoint for AMM symbols."
        )

    existing = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = $2",
        request.symbol, request.engine_type.value,
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol '{request.symbol}' with engine_type CLOB already exists")

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
    return result


async def create_pool(request: CreatePoolRequest, router: EngineRouter) -> dict:
    """Create a new AMM pool with auto-created symbol."""
    db = get_db()

    existing = await db.read_one(
        "SELECT symbol_id FROM symbol_configs WHERE symbol = $1 AND engine_type = $2",
        request.symbol, EngineType.AMM.value,
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Symbol '{request.symbol}' with engine_type AMM already exists")

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

    return {
        "symbol": symbol_result,
        "pool": pool_result,
        "pool_id": pool_id,
        "protocol_lp_shares": float(protocol_lp_shares),
    }


async def update_symbol_status(symbol: str, status: SymbolStatus, router: EngineRouter) -> dict:
    """Update symbol trading status."""
    db = get_db()
    is_active = status == SymbolStatus.ACTIVE

    result = await db.execute(
        "UPDATE symbol_configs SET is_active = $2, updated_at = NOW() WHERE symbol = $1",
        symbol.upper(), is_active,
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    router.invalidate_cache(symbol.upper())
    return {"symbol": symbol.upper(), "is_active": is_active}


async def delete_symbol(symbol: str, router: EngineRouter) -> dict:
    """Soft delete a symbol."""
    db = get_db()

    result = await db.execute(
        "UPDATE symbol_configs SET is_active = FALSE, updated_at = NOW() WHERE symbol = $1",
        symbol.upper(),
    )
    if "UPDATE 0" in result:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    router.invalidate_cache(symbol.upper())
    return {"symbol": symbol.upper(), "deleted": True}


async def get_audit_log(
    admin_id: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Query admin audit log with pagination and filters."""
    db = get_db()

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

    total = await db.read_one(
        f"SELECT COUNT(*) as count FROM admin_audit_logs aal WHERE {where_clause}",
        *params,
    )

    logs = await db.read(
        f"""
        SELECT
            aal.id, aal.admin_id, a.name as admin_name, a.email as admin_email,
            aal.action, aal.target_type, aal.target_id, aal.details, aal.created_at
        FROM admin_audit_logs aal
        JOIN admins a ON aal.admin_id = a.admin_id
        WHERE {where_clause}
        ORDER BY aal.created_at DESC
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return {
        "logs": logs,
        "total": total["count"] if total else 0,
        "limit": limit,
        "offset": offset,
    }
