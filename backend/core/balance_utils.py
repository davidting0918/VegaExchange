"""
DEPRECATED: Balance utilities have been moved to backend/services/user.py.

This file re-exports for backward compatibility during migration.
"""

from backend.services.user import (  # noqa: F401
    DEFAULT_BALANCES,
    create_initial_balances,
    get_user_balance,
    get_user_balances,
)
