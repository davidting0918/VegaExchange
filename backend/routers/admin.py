"""
Admin API Routes — thin router, delegates to domain services.

All endpoints require admin permissions.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.audit_log import AuditContext, AuditOp, audit_logged, get_audit_context
from backend.core.auth import require_admin
from backend.core.dependencies import get_router
from backend.engines.engine_router import EngineRouter
from backend.models.common import APIResponse
from backend.models.enums import SymbolStatus
from backend.models.admin import (
    AddWhitelistRequest,
    CreatePoolRequest,
    CreateSymbolRequest,
    UpdateSettingRequest,
    UpdateSymbolRequest,
    UpdateUserBalanceRequest,
    UpdateUserStatusRequest,
)
from backend.services import admin as admin_service
from backend.services import market as market_service
from backend.services import pool as pool_service
from backend.services import user as user_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


# =============================================================================
# Symbol Management
# =============================================================================

@router.post("/create_symbol", response_model=APIResponse)
@audit_logged(action="create_symbol", target_type="symbol", op=AuditOp.CREATE)
async def create_symbol(
    request: CreateSymbolRequest,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Create a new trading symbol (CLOB only). Requires admin permissions."""
    result = await admin_service.create_symbol(request, router)
    audit.set(
        target_id=str(result["symbol_id"]),
        new={
            "symbol": request.symbol,
            "base": request.base_asset,
            "quote": request.quote_asset,
            "market": request.market,
            "settle": request.settle or request.quote_asset,
            "engine_type": request.engine_type.value,
            "min_trade_amount": request.min_trade_amount,
            "max_trade_amount": request.max_trade_amount,
            "price_precision": request.price_precision,
            "quantity_precision": request.quantity_precision,
            "init_price": request.init_price,
        },
    )
    return APIResponse(success=True, data=result)


@router.post("/create_pool", response_model=APIResponse)
@audit_logged(action="create_pool", target_type="pool", op=AuditOp.CREATE)
async def create_pool(
    request: CreatePoolRequest,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Create a new AMM pool (auto-creates symbol). Requires admin permissions."""
    result = await admin_service.create_pool(request, router)
    audit.set(
        target_id=result["pool_id"],
        new={
            "symbol": request.symbol,
            "base": request.base_asset,
            "quote": request.quote_asset,
            "market": request.market,
            "settle": request.settle or request.quote_asset,
            "symbol_id": result["symbol"]["symbol_id"],
            "initial_reserve_base": request.initial_reserve_base,
            "initial_reserve_quote": request.initial_reserve_quote,
            "fee_rate": request.fee_rate,
            "min_trade_amount": request.min_trade_amount,
            "max_trade_amount": request.max_trade_amount,
            "price_precision": request.price_precision,
            "quantity_precision": request.quantity_precision,
        },
    )
    return APIResponse(success=True, data=result)


@router.post("/update_symbol_status/{symbol}", response_model=APIResponse)
@audit_logged(action="update_symbol_status", target_type="symbol", op=AuditOp.UPDATE)
async def update_symbol_status(
    symbol: str,
    status: SymbolStatus = Query(..., description="Symbol status (ACTIVE or MAINTENANCE)"),
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Update symbol trading status. Requires admin permissions."""
    result = await admin_service.update_symbol_status(symbol, status, router)
    audit.set(
        target_id=result["symbol"],
        old={"is_active": result["prev_is_active"]},
        new={"is_active": result["is_active"]},
    )
    return APIResponse(success=True, data=result)


@router.post("/delete_symbol/{symbol}", response_model=APIResponse)
@audit_logged(action="delete_symbol", target_type="symbol", op=AuditOp.DELETE)
async def delete_symbol(
    symbol: str,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Delete a symbol (soft delete). Requires admin permissions."""
    result = await admin_service.delete_symbol(symbol, router)
    audit.set(
        target_id=result["symbol"],
        old=result["prev_row"],
    )
    return APIResponse(success=True, data=result)


@router.get("/symbols", response_model=APIResponse)
async def get_symbols(
    engine_type: Optional[int] = Query(None, description="Filter by engine type: 0=AMM, 1=CLOB"),
    is_active: Optional[bool] = Query(None, description="Filter by active status (null=all)"),
    market: Optional[str] = Query(None, description="Filter by market type"),
    current_admin: dict = Depends(require_admin),
):
    """Get all symbols with full config. Reuses market_service.get_symbols with is_active=None to include inactive."""
    data = await market_service.get_symbols(engine_type, is_active, market)
    return APIResponse(success=True, data=data)


@router.get("/symbols/{symbol_id}", response_model=APIResponse)
async def get_symbol(
    symbol_id: int,
    current_admin: dict = Depends(require_admin),
):
    """Get detailed symbol config + associated pool data."""
    data = await market_service.get_symbol_by_id(symbol_id)
    return APIResponse(success=True, data=data)


@router.post("/symbols/update/{symbol_id}", response_model=APIResponse)
@audit_logged(action="update_symbol_config", target_type="symbol", op=AuditOp.UPDATE)
async def update_symbol(
    symbol_id: int,
    request: UpdateSymbolRequest,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Update mutable fields of a symbol config."""
    result = await admin_service.update_symbol(symbol_id, request, router)
    audit.set(
        target_id=str(symbol_id),
        old=result["audit_old"],
        new=result["audit_new"],
    )
    return APIResponse(success=True, data=result["symbol"])


# =============================================================================
# Pool Management — reuses pool_service
# =============================================================================

@router.get("/pools", response_model=APIResponse)
async def get_admin_pools(current_admin: dict = Depends(require_admin)):
    """Get all AMM pools with enriched data (TVL, price, volume)."""
    data = await pool_service.get_all_pools_enriched()
    return APIResponse(success=True, data=data)


@router.get("/pools/{pool_id}", response_model=APIResponse)
async def get_admin_pool(
    pool_id: str,
    current_admin: dict = Depends(require_admin),
):
    """Get detailed pool info + LP positions + recent swaps."""
    data = await pool_service.get_pool_detail(pool_id)
    return APIResponse(success=True, data=data)


# =============================================================================
# User Management — reuses user_service for reads
# =============================================================================

@router.get("/users", response_model=APIResponse)
async def get_admin_users(
    search: Optional[str] = Query(None, description="Search by email or username"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(20, ge=1, le=100, description="Page size"),
    offset: int = Query(0, ge=0, description="Offset"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    current_admin: dict = Depends(require_admin),
):
    """Get paginated user list with summary info."""
    data = await admin_service.get_admin_users(
        search=search, is_active=is_active,
        limit=limit, offset=offset,
        sort_by=sort_by, sort_order=sort_order,
    )
    return APIResponse(success=True, data=data)


@router.get("/users/{user_id}", response_model=APIResponse)
async def get_admin_user(
    user_id: str,
    current_admin: dict = Depends(require_admin),
):
    """Get full user profile + balances + recent trades."""
    user = await user_service.get_user_info(user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    balances = await user_service.get_user_balances(user_id, include_total=True)
    trades = await user_service.get_user_trades(user_id, limit=50)

    return APIResponse(success=True, data={"user": user, "balances": balances, "trades": trades})


@router.post("/users/{user_id}/balance/update", response_model=APIResponse)
@audit_logged(action="update_user_balance", target_type="user", op=AuditOp.UPDATE)
async def update_user_balance(
    user_id: str,
    request: UpdateUserBalanceRequest,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Adjust a user's balance (absolute value)."""
    result = await admin_service.update_user_balance(user_id, request.currency, request.available)
    audit.set(
        target_id=user_id,
        old={"currency": result["currency"], "available": result["old_available"]},
        new={"currency": result["currency"], "available": result["new_available"]},
    )
    return APIResponse(success=True, data=result)


@router.post("/users/{user_id}/status/update", response_model=APIResponse)
@audit_logged(action="update_user_status", target_type="user", op=AuditOp.UPDATE)
async def update_user_status(
    user_id: str,
    request: UpdateUserStatusRequest,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Enable/disable a user account. Revokes tokens when disabling."""
    result = await admin_service.update_user_status(user_id, request.is_active)
    audit.set(
        target_id=user_id,
        old={"is_active": result["prev_is_active"]},
        new={"is_active": result["is_active"], "tokens_revoked": result["tokens_revoked"]},
    )
    return APIResponse(success=True, data=result)


@router.post("/users/{user_id}/reset-balances", response_model=APIResponse)
@audit_logged(action="reset_user_balances", target_type="user", op=AuditOp.UPDATE)
async def reset_user_balances(
    user_id: str,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Reset user balances to platform defaults."""
    result = await admin_service.reset_user_balances(user_id)
    audit.set(
        target_id=user_id,
        old=result["prev_balances"],
        new=result["new_balances"],
    )
    return APIResponse(success=True, data=result)


# =============================================================================
# Platform Settings
# =============================================================================

@router.get("/settings", response_model=APIResponse)
async def get_settings(current_admin: dict = Depends(require_admin)):
    """Get all platform settings."""
    data = await admin_service.get_settings()
    return APIResponse(success=True, data=data)


@router.post("/settings/update/{key}", response_model=APIResponse)
@audit_logged(action="update_setting", target_type="setting", op=AuditOp.UPDATE)
async def update_setting(
    key: str,
    request: UpdateSettingRequest,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Update a platform setting."""
    result = await admin_service.update_setting(key, request.value)
    audit.set(
        target_id=key,
        old={"value": result["old_value"]},
        new={"value": request.value},
    )
    return APIResponse(success=True, data=result["setting"])


# =============================================================================
# Admin Whitelist
# =============================================================================

@router.get("/whitelist", response_model=APIResponse)
async def get_whitelist(current_admin: dict = Depends(require_admin)):
    """Get all admin whitelist entries."""
    data = await admin_service.get_whitelist()
    return APIResponse(success=True, data=data)


@router.post("/whitelist", response_model=APIResponse)
@audit_logged(action="add_whitelist", target_type="whitelist", op=AuditOp.CREATE)
async def add_whitelist(
    request: AddWhitelistRequest,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Add an email to admin whitelist."""
    result = await admin_service.add_whitelist(request.email, request.description)
    audit.set(
        target_id=str(result["id"]),
        new={
            "id": result["id"],
            "email": request.email,
            "description": request.description,
        },
    )
    return APIResponse(success=True, data=result)


@router.post("/whitelist/remove/{whitelist_id}", response_model=APIResponse)
@audit_logged(action="remove_whitelist", target_type="whitelist", op=AuditOp.DELETE)
async def remove_whitelist(
    whitelist_id: int,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Remove an email from admin whitelist."""
    result = await admin_service.remove_whitelist(whitelist_id)
    audit.set(
        target_id=str(whitelist_id),
        old={
            "id": result["id"],
            "email": result["email"],
            "description": result.get("description"),
        },
    )
    return APIResponse(success=True, data=result)


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
    """Query admin audit log with pagination and filters."""
    data = await admin_service.get_audit_log(
        admin_id=admin_id, action=action, target_type=target_type,
        date_from=date_from, date_to=date_to, limit=limit, offset=offset,
    )
    return APIResponse(success=True, data=data)


# =============================================================================
# Dashboard — stats + recent activity combined
# =============================================================================

@router.get("/dashboard", response_model=APIResponse)
async def get_dashboard(
    period: str = Query("7d", description="Activity period: 7d or 30d"),
    current_admin: dict = Depends(require_admin),
):
    """Get platform stats + recent activity in one call."""
    data = await admin_service.get_dashboard(period)
    return APIResponse(success=True, data=data)
