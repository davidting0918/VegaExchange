"""
User domain models — user info, balances, portfolio.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    """User information response"""

    user_id: str
    email: str
    user_name: Optional[str] = None
    photo_url: Optional[str] = None
    is_admin: bool = False
    created_at: datetime
    last_login_at: datetime


class BalanceResponse(BaseModel):
    """User balance for a single currency"""

    currency: str
    available: Decimal
    locked: Decimal
    total: Decimal = Field(description="available + locked")
