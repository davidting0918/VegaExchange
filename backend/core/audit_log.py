"""
Admin audit log utility for VegaExchange.

Uses a decorator pattern with AuditContext dependency. The decorator declares
the operation type (CREATE / UPDATE / DELETE) and automatically wraps the
endpoint-supplied data into a uniform `{"old": ..., "new": ...}` shape:

    @router.post("/create_symbol", response_model=APIResponse)
    @audit_logged(action="create_symbol", target_type="symbol", op=AuditOp.CREATE)
    async def create_symbol(
        ...,
        current_admin: dict = Depends(require_admin),
        audit: AuditContext = Depends(get_audit_context),
    ):
        result = await admin_service.create_symbol(request, router)
        audit.set(target_id=str(result["symbol_id"]), new={...})
        return APIResponse(...)

CRUD shape rules enforced by the decorator:
    - CREATE: requires `new=`; persists `{"old": None, "new": new}`
    - UPDATE: requires `old=` and `new=`; diffs and persists only changed fields
    - DELETE: requires `old=`; persists `{"old": old, "new": None}`

For non-CRUD actions, omit the `op` parameter and use `audit.set(details=...)`
as a raw escape hatch.

The decorator automatically logs the action after successful execution.
Audit logging failures are caught — they must never break the main operation.
"""

import inspect
import json
import traceback
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import Any, Optional, Tuple

import asyncpg

from backend.core.db_manager import get_db


class AuditOp(str, Enum):
    """Operation type for an audited admin action."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class AuditContext:
    """Mutable context that an endpoint populates with audit metadata."""

    def __init__(self):
        self.target_id: Optional[str] = None
        self.old: Optional[dict] = None
        self.new: Optional[dict] = None
        self.raw_details: Optional[dict] = None

    def set(
        self,
        target_id: str,
        *,
        old: Optional[dict] = None,
        new: Optional[dict] = None,
        details: Optional[dict] = None,
    ) -> None:
        """
        Populate audit metadata for the current request.

        For CRUD endpoints (decorator declares `op`), pass `old` and/or `new`.
        For non-CRUD endpoints, pass `details` as a raw dict.
        """
        self.target_id = target_id
        self.old = old
        self.new = new
        self.raw_details = details


def get_audit_context() -> AuditContext:
    """FastAPI dependency that provides a fresh AuditContext per request."""
    return AuditContext()


def _diff_changed_fields(old: dict, new: dict) -> Tuple[dict, dict]:
    """
    Return (old_changed, new_changed) containing only keys whose values differ
    between old and new. Keys present in only one side are also considered
    changed and included with `None` on the missing side.
    """
    changed_old: dict = {}
    changed_new: dict = {}
    for key in set(old.keys()) | set(new.keys()):
        old_val = old.get(key)
        new_val = new.get(key)
        if old_val != new_val:
            changed_old[key] = old_val
            changed_new[key] = new_val
    return changed_old, changed_new


def _audit_json_default(obj: Any) -> Any:
    """JSON encoder hook for types commonly returned by services."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, asyncpg.Record):
        return dict(obj)
    if isinstance(obj, Enum):
        return obj.value
    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable for audit log")


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
        details_json = (
            json.dumps(details, default=_audit_json_default) if details is not None else None
        )
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


def _build_details(action: str, op: Optional[AuditOp], audit: AuditContext) -> Optional[dict]:
    """Construct the details dict to persist based on the operation type."""
    if op is None:
        # Non-CRUD escape hatch
        return audit.raw_details

    if op == AuditOp.CREATE:
        if audit.new is None:
            raise RuntimeError(
                f"Audit op CREATE on action='{action}' requires audit.set(new=...)"
            )
        return {"old": None, "new": audit.new}

    if op == AuditOp.UPDATE:
        if audit.old is None or audit.new is None:
            raise RuntimeError(
                f"Audit op UPDATE on action='{action}' requires audit.set(old=..., new=...)"
            )
        old_diff, new_diff = _diff_changed_fields(audit.old, audit.new)
        return {"old": old_diff, "new": new_diff}

    if op == AuditOp.DELETE:
        if audit.old is None:
            raise RuntimeError(
                f"Audit op DELETE on action='{action}' requires audit.set(old=...)"
            )
        return {"old": audit.old, "new": None}

    raise RuntimeError(f"Unknown audit op: {op}")


def audit_logged(action: str, target_type: str, op: Optional[AuditOp] = None):
    """
    Decorator that logs admin actions after successful endpoint execution.

    The decorated endpoint must have these keyword arguments:
    - current_admin: dict  (from Depends(require_admin))
    - audit: AuditContext   (from Depends(get_audit_context))

    Parameters:
        action: short identifier for the action (e.g. "create_symbol")
        target_type: resource type (e.g. "symbol", "user", "whitelist")
        op: optional CRUD operation type. When set, the decorator wraps
            audit.old / audit.new into a `{"old": ..., "new": ...}` payload
            and validates that the endpoint provided the required sides.
            When None, the endpoint must call audit.set(details=...) and
            the raw dict is persisted as-is.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            response = await func(*args, **kwargs)

            current_admin = kwargs.get("current_admin")
            audit: Optional[AuditContext] = kwargs.get("audit")

            if current_admin and audit and audit.target_id is not None:
                try:
                    details = _build_details(action, op, audit)
                except RuntimeError:
                    # Bad audit shape — log and skip writing
                    print(f"[WARN] Audit shape error for action '{action}'")
                    traceback.print_exc()
                    return response

                await _write_audit_log(
                    admin_id=current_admin["admin_id"],
                    action=action,
                    target_type=target_type,
                    target_id=audit.target_id,
                    details=details,
                )

            return response

        # Preserve original function signature so FastAPI can inspect parameters
        wrapper.__signature__ = inspect.signature(func)
        return wrapper

    return decorator
