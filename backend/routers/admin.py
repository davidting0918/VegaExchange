"""
Admin API Routes — thin router, delegates to services/admin.py.

All endpoints require admin permissions.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.core.audit_log import AuditContext, audit_logged, get_audit_context
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
)
from backend.services import admin as admin_service

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
    """Create a new trading symbol (CLOB only). Requires admin permissions."""
    result = await admin_service.create_symbol(request, router)
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
    """Create a new AMM pool (auto-creates symbol). Requires admin permissions."""
    result = await admin_service.create_pool(request, router)
    audit.set(
        target_id=result["pool_id"],
        details={"symbol": request.symbol, "symbol_id": result["symbol"]["symbol_id"], "fee_rate": float(request.fee_rate)},
    )
    return APIResponse(success=True, data=result)


@router.post("/update_symbol_status/{symbol}", response_model=APIResponse)
@audit_logged(action="update_symbol_status", target_type="symbol")
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
        details={"new_status": "active" if result["is_active"] else "maintenance"},
    )
    return APIResponse(success=True, data=result)


@router.post("/delete_symbol/{symbol}", response_model=APIResponse)
@audit_logged(action="delete_symbol", target_type="symbol")
async def delete_symbol(
    symbol: str,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Delete a symbol (soft delete). Requires admin permissions."""
    result = await admin_service.delete_symbol(symbol, router)
    audit.set(target_id=result["symbol"])
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
# Symbol CRUD (#31)
# =============================================================================

@router.get("/symbols", response_model=APIResponse)
async def get_symbols(
    engine_type: Optional[int] = Query(None, description="Filter by engine type: 0=AMM, 1=CLOB"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    market: Optional[str] = Query(None, description="Filter by market type"),
    current_admin: dict = Depends(require_admin),
):
    """Get all symbols with full config. Includes pool info for AMM symbols."""
    data = await admin_service.get_symbols(engine_type, is_active, market)
    return APIResponse(success=True, data=data)


@router.get("/symbols/{symbol_id}", response_model=APIResponse)
async def get_symbol(
    symbol_id: int,
    current_admin: dict = Depends(require_admin),
):
    """Get detailed symbol config + associated pool data."""
    data = await admin_service.get_symbol(symbol_id)
    return APIResponse(success=True, data=data)


@router.put("/symbols/{symbol_id}", response_model=APIResponse)
@audit_logged(action="update_symbol_config", target_type="symbol")
async def update_symbol(
    symbol_id: int,
    request: UpdateSymbolRequest,
    router: EngineRouter = Depends(get_router),
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Update mutable fields of a symbol config. For AMM symbols, also updates pool fee_rate."""
    data = await admin_service.update_symbol(symbol_id, request, router)
    audit.set(
        target_id=str(symbol_id),
        details={k: v for k, v in request.model_dump(exclude_none=True).items()},
    )
    return APIResponse(success=True, data=data)


# =============================================================================
# Platform Settings (#34)
# =============================================================================

@router.get("/settings", response_model=APIResponse)
async def get_settings(current_admin: dict = Depends(require_admin)):
    """Get all platform settings."""
    data = await admin_service.get_settings()
    return APIResponse(success=True, data=data)


@router.put("/settings/{key}", response_model=APIResponse)
@audit_logged(action="update_setting", target_type="setting")
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
        details={"old": result["old_value"], "new": request.value},
    )
    return APIResponse(success=True, data=result["setting"])


# =============================================================================
# Admin Whitelist (#34)
# =============================================================================

@router.get("/whitelist", response_model=APIResponse)
async def get_whitelist(current_admin: dict = Depends(require_admin)):
    """Get all admin whitelist entries."""
    data = await admin_service.get_whitelist()
    return APIResponse(success=True, data=data)


@router.post("/whitelist", response_model=APIResponse)
@audit_logged(action="add_whitelist", target_type="whitelist")
async def add_whitelist(
    request: AddWhitelistRequest,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Add an email to admin whitelist."""
    result = await admin_service.add_whitelist(request.email, request.description)
    audit.set(
        target_id=str(result["id"]),
        details={"email": request.email},
    )
    return APIResponse(success=True, data=result)


@router.delete("/whitelist/{whitelist_id}", response_model=APIResponse)
@audit_logged(action="remove_whitelist", target_type="whitelist")
async def remove_whitelist(
    whitelist_id: int,
    current_admin: dict = Depends(require_admin),
    audit: AuditContext = Depends(get_audit_context),
):
    """Remove an email from admin whitelist."""
    result = await admin_service.remove_whitelist(whitelist_id)
    audit.set(
        target_id=str(whitelist_id),
        details={"email": result["email"]},
    )
    return APIResponse(success=True, data=result)
