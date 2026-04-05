"""
Admin domain service — symbol CRUD, pool admin, settings, whitelist, audit log queries.
"""

import json
from decimal import Decimal
from math import sqrt
from typing import Any, List, Optional

from fastapi import HTTPException

from backend.core.db_manager import get_db
from backend.core.id_generator import generate_pool_id
from backend.engines.engine_router import EngineRouter
from backend.models.enums import EngineType, SymbolStatus
from backend.models.admin import CreatePoolRequest, CreateSymbolRequest, UpdateSymbolRequest


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


# =============================================================================
# Symbol CRUD (#31)
# =============================================================================

async def get_symbols(
    engine_type: Optional[int] = None,
    is_active: Optional[bool] = None,
    market: Optional[str] = None,
) -> List[dict]:
    """Get all symbols with full config, optionally filtered. Includes pool info for AMM symbols."""
    db = get_db()

    conditions = []
    params: list = []
    param_idx = 1

    if engine_type is not None:
        conditions.append(f"sc.engine_type = ${param_idx}")
        params.append(engine_type)
        param_idx += 1

    if is_active is not None:
        conditions.append(f"sc.is_active = ${param_idx}")
        params.append(is_active)
        param_idx += 1

    if market:
        conditions.append(f"sc.market = ${param_idx}")
        params.append(market.upper())
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    symbols = await db.read(
        f"""
        SELECT sc.*,
               ap.pool_id, ap.reserve_base, ap.reserve_quote, ap.fee_rate,
               ap.total_lp_shares, ap.total_volume_quote, ap.total_fees_collected,
               CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE NULL END as current_price,
               CASE WHEN ap.reserve_quote IS NOT NULL THEN ap.reserve_quote * 2 ELSE NULL END as tvl_usdt
        FROM symbol_configs sc
        LEFT JOIN amm_pools ap ON sc.symbol_id = ap.symbol_id
        WHERE {where_clause}
        ORDER BY sc.created_at DESC
        """,
        *params,
    )

    return symbols


async def get_symbol(symbol_id: int) -> dict:
    """Get detailed symbol config + associated pool data (if AMM)."""
    db = get_db()

    symbol = await db.read_one(
        """
        SELECT sc.*,
               ap.pool_id, ap.reserve_base, ap.reserve_quote, ap.k_value,
               ap.fee_rate, ap.total_lp_shares, ap.total_volume_base, ap.total_volume_quote,
               ap.total_fees_collected, ap.is_active as pool_is_active,
               CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE NULL END as current_price,
               CASE WHEN ap.reserve_quote IS NOT NULL THEN ap.reserve_quote * 2 ELSE NULL END as tvl_usdt
        FROM symbol_configs sc
        LEFT JOIN amm_pools ap ON sc.symbol_id = ap.symbol_id
        WHERE sc.symbol_id = $1
        """,
        symbol_id,
    )

    if not symbol:
        raise HTTPException(status_code=404, detail=f"Symbol with id {symbol_id} not found")

    return symbol


async def update_symbol(symbol_id: int, request: UpdateSymbolRequest, router: EngineRouter) -> dict:
    """Update mutable fields of a symbol config. For AMM symbols, also update pool fee_rate."""
    db = get_db()

    # Verify symbol exists
    existing = await db.read_one(
        "SELECT * FROM symbol_configs WHERE symbol_id = $1",
        symbol_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"Symbol with id {symbol_id} not found")

    # Build SET clause for symbol_configs
    updates = []
    params: list = []
    param_idx = 1

    if request.engine_params is not None:
        updates.append(f"engine_params = ${param_idx}::jsonb")
        params.append(json.dumps(request.engine_params))
        param_idx += 1

    if request.min_trade_amount is not None:
        updates.append(f"min_trade_amount = ${param_idx}")
        params.append(request.min_trade_amount)
        param_idx += 1

    if request.max_trade_amount is not None:
        updates.append(f"max_trade_amount = ${param_idx}")
        params.append(request.max_trade_amount)
        param_idx += 1

    if request.price_precision is not None:
        updates.append(f"price_precision = ${param_idx}")
        params.append(request.price_precision)
        param_idx += 1

    if request.quantity_precision is not None:
        updates.append(f"quantity_precision = ${param_idx}")
        params.append(request.quantity_precision)
        param_idx += 1

    if updates:
        updates.append("updated_at = NOW()")
        set_clause = ", ".join(updates)
        params.append(symbol_id)
        await db.execute(
            f"UPDATE symbol_configs SET {set_clause} WHERE symbol_id = ${param_idx}",
            *params,
        )

    # Update AMM pool fee_rate if provided and symbol is AMM
    if request.fee_rate is not None and existing["engine_type"] == EngineType.AMM.value:
        await db.execute(
            "UPDATE amm_pools SET fee_rate = $1 WHERE symbol_id = $2",
            request.fee_rate,
            symbol_id,
        )

    # Invalidate engine cache
    router.invalidate_cache(existing["symbol"])

    # Return updated symbol
    return await get_symbol(symbol_id)


# =============================================================================
# Platform Settings (#34)
# =============================================================================

async def get_settings() -> List[dict]:
    """Get all platform settings."""
    db = get_db()
    return await db.read("SELECT * FROM platform_settings ORDER BY key")


async def update_setting(key: str, value: Any) -> dict:
    """Update a platform setting. Returns old and new values."""
    db = get_db()

    existing = await db.read_one(
        "SELECT * FROM platform_settings WHERE key = $1",
        key,
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    old_value = existing["value"]

    await db.execute(
        "UPDATE platform_settings SET value = $1::jsonb, updated_at = NOW() WHERE key = $2",
        json.dumps(value),
        key,
    )

    updated = await db.read_one("SELECT * FROM platform_settings WHERE key = $1", key)
    return {"setting": updated, "old_value": old_value}


# =============================================================================
# Admin Whitelist (#34)
# =============================================================================

async def get_whitelist() -> List[dict]:
    """Get all admin whitelist entries."""
    db = get_db()
    return await db.read("SELECT * FROM admin_whitelist ORDER BY created_at DESC")


async def add_whitelist(email: str, description: Optional[str] = None) -> dict:
    """Add an email to admin whitelist."""
    db = get_db()

    existing = await db.read_one(
        "SELECT id FROM admin_whitelist WHERE email = $1",
        email.lower(),
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Email '{email}' is already in whitelist")

    result = await db.execute_returning(
        """
        INSERT INTO admin_whitelist (email, description)
        VALUES ($1, $2)
        RETURNING *
        """,
        email.lower(),
        description,
    )
    return result


async def remove_whitelist(whitelist_id: int) -> dict:
    """Remove an email from admin whitelist by ID."""
    db = get_db()

    existing = await db.read_one(
        "SELECT * FROM admin_whitelist WHERE id = $1",
        whitelist_id,
    )
    if not existing:
        raise HTTPException(status_code=404, detail=f"Whitelist entry {whitelist_id} not found")

    await db.execute("DELETE FROM admin_whitelist WHERE id = $1", whitelist_id)
    return existing


# =============================================================================
# Pool Management (#32)
# =============================================================================

async def get_admin_pools() -> List[dict]:
    """Get all AMM pools with enriched data for admin view."""
    db = get_db()

    pools = await db.read(
        """
        SELECT
            ap.pool_id, sc.symbol, sc.symbol_id, sc.base, sc.quote,
            ap.reserve_base, ap.reserve_quote, ap.k_value, ap.fee_rate,
            ap.total_lp_shares, ap.total_volume_base, ap.total_volume_quote,
            ap.total_fees_collected, ap.is_active,
            CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE 0 END as price,
            ap.reserve_quote * 2 as tvl_usdt,
            ap.created_at, ap.updated_at
        FROM amm_pools ap
        JOIN symbol_configs sc ON ap.symbol_id = sc.symbol_id
        ORDER BY ap.reserve_quote * 2 DESC
        """
    )
    return pools


async def get_admin_pool(pool_id: str) -> dict:
    """Get detailed pool info + LP positions + recent swaps."""
    db = get_db()

    pool = await db.read_one(
        """
        SELECT
            ap.*, sc.symbol, sc.base, sc.quote, sc.market, sc.settle,
            CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE 0 END as price,
            ap.reserve_quote * 2 as tvl_usdt
        FROM amm_pools ap
        JOIN symbol_configs sc ON ap.symbol_id = sc.symbol_id
        WHERE ap.pool_id = $1
        """,
        pool_id,
    )
    if not pool:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found")

    # LP positions
    lp_positions = await db.read(
        """
        SELECT lp.user_id, u.user_name, lp.lp_shares,
               CASE WHEN $2 > 0 THEN lp.lp_shares / $2 * 100 ELSE 0 END as share_pct
        FROM lp_positions lp
        JOIN users u ON lp.user_id = u.user_id
        WHERE lp.pool_id = $1 AND lp.lp_shares > 0
        ORDER BY lp.lp_shares DESC
        """,
        pool_id,
        pool["total_lp_shares"],
    )

    # Recent swaps
    recent_swaps = await db.read(
        """
        SELECT t.trade_id, t.user_id, t.side, t.price, t.quantity,
               t.quote_amount, t.fee_amount, t.fee_asset, t.created_at
        FROM trades t
        WHERE t.symbol_id = $1 AND t.engine_type = 0 AND t.status = 1
        ORDER BY t.created_at DESC
        LIMIT 20
        """,
        pool["symbol_id"],
    )

    return {
        "pool": pool,
        "lp_positions": lp_positions,
        "recent_swaps": recent_swaps,
    }


# =============================================================================
# User Management (#33)
# =============================================================================

async def get_admin_users(
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict:
    """Get paginated user list with summary info."""
    db = get_db()

    # Validate sort_by to prevent SQL injection
    allowed_sort = {"created_at", "last_login_at", "user_name", "email"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"

    conditions = []
    params: list = []
    param_idx = 1

    if search:
        conditions.append(f"(u.email ILIKE ${param_idx} OR u.user_name ILIKE ${param_idx})")
        params.append(f"%{search}%")
        param_idx += 1

    if is_active is not None:
        conditions.append(f"u.is_active = ${param_idx}")
        params.append(is_active)
        param_idx += 1

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    total = await db.read_one(
        f"SELECT COUNT(*) as count FROM users u WHERE {where_clause}",
        *params,
    )

    users = await db.read(
        f"""
        SELECT u.user_id, u.user_name, u.email, u.is_active,
               u.created_at, u.last_login_at,
               (SELECT COUNT(*) FROM trades t WHERE t.user_id = u.user_id) as trade_count
        FROM users u
        WHERE {where_clause}
        ORDER BY u.{sort_by} {sort_dir}
        LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """,
        *params, limit, offset,
    )

    return {
        "users": users,
        "total": total["count"] if total else 0,
        "limit": limit,
        "offset": offset,
    }


async def get_admin_user(user_id: str) -> dict:
    """Get full user profile + balances + recent trades."""
    db = get_db()

    user = await db.read_one("SELECT * FROM users WHERE user_id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    balances = await db.read(
        """
        SELECT currency, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1 AND account_type = 'spot'
        ORDER BY currency
        """,
        user_id,
    )

    trades = await db.read(
        """
        SELECT t.*, sc.symbol
        FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE t.user_id = $1
        ORDER BY t.created_at DESC
        LIMIT 50
        """,
        user_id,
    )

    return {"user": user, "balances": balances, "trades": trades}


async def update_user_balance(user_id: str, currency: str, available: Decimal) -> dict:
    """Set a user's balance to an absolute value. Returns old and new values."""
    db = get_db()

    old_balance = await db.read_one(
        """
        SELECT available FROM user_balances
        WHERE user_id = $1 AND currency = $2 AND account_type = 'spot'
        """,
        user_id, currency.upper(),
    )
    if not old_balance:
        raise HTTPException(status_code=404, detail=f"Balance for {currency} not found for user {user_id}")

    old_value = old_balance["available"]

    await db.execute(
        """
        UPDATE user_balances SET available = $1, updated_at = NOW()
        WHERE user_id = $2 AND currency = $3 AND account_type = 'spot'
        """,
        available, user_id, currency.upper(),
    )

    return {"old_available": old_value, "new_available": available, "currency": currency.upper()}


async def update_user_status(user_id: str, is_active: bool) -> dict:
    """Enable/disable a user account. Revokes tokens when disabling."""
    db = get_db()

    user = await db.read_one("SELECT user_id, is_active FROM users WHERE user_id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    await db.execute(
        "UPDATE users SET is_active = $1, updated_at = NOW() WHERE user_id = $2",
        is_active, user_id,
    )

    # Revoke all active tokens when disabling
    if not is_active:
        await db.execute(
            "UPDATE access_tokens SET is_active = FALSE WHERE user_id = $1 AND is_active = TRUE",
            user_id,
        )

    return {"user_id": user_id, "is_active": is_active, "tokens_revoked": not is_active}


async def reset_user_balances(user_id: str) -> dict:
    """Reset user balances to platform defaults from platform_settings."""
    db = get_db()

    user = await db.read_one("SELECT user_id FROM users WHERE user_id = $1", user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    # Read init_funding from platform_settings
    from backend.services.user import _get_init_funding
    funding = await _get_init_funding()

    for currency, amount in funding.items():
        await db.execute(
            """
            UPDATE user_balances SET available = $1, locked = 0, updated_at = NOW()
            WHERE user_id = $2 AND currency = $3 AND account_type = 'spot'
            """,
            amount, user_id, currency,
        )

    return {"user_id": user_id, "reset_to": {k: float(v) for k, v in funding.items()}}


# =============================================================================
# Dashboard Stats (#30)
# =============================================================================

async def get_dashboard_stats() -> dict:
    """Get aggregated platform statistics."""
    db = get_db()

    total_users = await db.read_one("SELECT COUNT(*) as count FROM users")
    active_users_24h = await db.read_one(
        "SELECT COUNT(*) as count FROM users WHERE last_login_at > NOW() - INTERVAL '24 hours'"
    )
    new_users_7d = await db.read_one(
        "SELECT COUNT(*) as count FROM users WHERE created_at > NOW() - INTERVAL '7 days'"
    )
    total_symbols = await db.read_one("SELECT COUNT(*) as count FROM symbol_configs")
    active_symbols = await db.read_one(
        "SELECT COUNT(*) as count FROM symbol_configs WHERE is_active = TRUE"
    )
    total_pools = await db.read_one("SELECT COUNT(*) as count FROM amm_pools")
    trades_24h = await db.read_one(
        "SELECT COUNT(*) as count, COALESCE(SUM(quote_amount), 0) as volume FROM trades WHERE created_at > NOW() - INTERVAL '24 hours' AND status = 1"
    )
    pool_tvl = await db.read_one(
        "SELECT COALESCE(SUM(reserve_quote * 2), 0) as tvl FROM amm_pools WHERE is_active = TRUE"
    )

    return {
        "total_users": total_users["count"] if total_users else 0,
        "active_users_24h": active_users_24h["count"] if active_users_24h else 0,
        "new_users_7d": new_users_7d["count"] if new_users_7d else 0,
        "total_symbols": total_symbols["count"] if total_symbols else 0,
        "active_symbols": active_symbols["count"] if active_symbols else 0,
        "total_pools": total_pools["count"] if total_pools else 0,
        "total_trades_24h": trades_24h["count"] if trades_24h else 0,
        "total_volume_24h_usdt": float(trades_24h["volume"]) if trades_24h else 0,
        "total_pool_tvl_usdt": float(pool_tvl["tvl"]) if pool_tvl else 0,
    }


async def get_recent_activity(period: str = "7d") -> dict:
    """Get daily trade volume and new user counts for charts."""
    db = get_db()

    days = 30 if period == "30d" else 7

    daily_trades = await db.read(
        """
        SELECT date_trunc('day', created_at)::date as date,
               COUNT(*) as count,
               COALESCE(SUM(quote_amount), 0) as volume_usdt
        FROM trades
        WHERE created_at > NOW() - make_interval(days => $1)
          AND status = 1
        GROUP BY date_trunc('day', created_at)::date
        ORDER BY date ASC
        """,
        days,
    )

    daily_new_users = await db.read(
        """
        SELECT date_trunc('day', created_at)::date as date,
               COUNT(*) as count
        FROM users
        WHERE created_at > NOW() - make_interval(days => $1)
        GROUP BY date_trunc('day', created_at)::date
        ORDER BY date ASC
        """,
        days,
    )

    return {
        "daily_trades": daily_trades,
        "daily_new_users": daily_new_users,
        "period": period,
    }
