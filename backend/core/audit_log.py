"""
Admin audit log utility for VegaExchange.

Uses a decorator pattern with AuditContext dependency:

    @router.post("/create_symbol", response_model=APIResponse)
    @audit_logged(action="create_symbol", target_type="symbol")
    async def create_symbol(
        ...,
        current_admin: dict = Depends(require_admin),
        audit: AuditContext = Depends(get_audit_context),
    ):
        ...
        audit.set(target_id=str(result["symbol_id"]), details={...})
        return APIResponse(...)

The decorator automatically logs the action after successful execution.
Audit logging failures are caught — they must never break the main operation.
"""

import inspect
import json
import traceback
from functools import wraps
from typing import Optional

from backend.core.db_manager import get_db


class AuditContext:
    """Mutable context that an endpoint populates with audit metadata."""

    def __init__(self):
        self.target_id: Optional[str] = None
        self.details: Optional[dict] = None

    def set(self, target_id: str, details: Optional[dict] = None) -> None:
        self.target_id = target_id
        self.details = details


def get_audit_context() -> AuditContext:
    """FastAPI dependency that provides a fresh AuditContext per request."""
    return AuditContext()


async def _write_audit_log(
    admin_id: str,
    action: str,
    target_type: str,
    target_id: str,
    details: Optional[dict] = None,
) -> None:
    """Insert a row into admin_audit_logs. Never raises."""
    try:
        db = get_db()
        details_json = json.dumps(details) if details else None
        await db.execute(
            """
            INSERT INTO admin_audit_logs (admin_id, action, target_type, target_id, details)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            """,
            admin_id,
            action,
            target_type,
            target_id,
            details_json,
        )
    except Exception:
        print(f"[WARN] Failed to log admin action: {action} by {admin_id}")
        traceback.print_exc()


def audit_logged(action: str, target_type: str):
    """
    Decorator that logs admin actions after successful endpoint execution.

    The decorated endpoint must have these keyword arguments:
    - current_admin: dict  (from Depends(require_admin))
    - audit: AuditContext   (from Depends(get_audit_context))

    The endpoint calls audit.set(target_id=..., details=...) before returning.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)

            current_admin = kwargs.get("current_admin")
            audit: Optional[AuditContext] = kwargs.get("audit")

            if current_admin and audit and audit.target_id is not None:
                await _write_audit_log(
                    admin_id=current_admin["admin_id"],
                    action=action,
                    target_type=target_type,
                    target_id=audit.target_id,
                    details=audit.details,
                )

            return response

        # Preserve original function signature so FastAPI can inspect parameters
        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return decorator
