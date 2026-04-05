"""
User Information API Routes

Thin router — delegates all business logic to services/user.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.core.auth import get_current_user, get_current_user_id
from backend.models.common import APIResponse
from backend.models.enums import EngineType
from backend.services import user as user_service

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("", response_model=APIResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information."""
    return APIResponse(success=True, data=current_user)


@router.get("/balances", response_model=APIResponse)
async def get_user_balances(user_id: str = Depends(get_current_user_id)):
    """Get all balances for the current user."""
    balances = await user_service.get_user_balances(user_id, include_total=True)
    return APIResponse(success=True, data=balances)


@router.get("/balance/{asset}", response_model=APIResponse)
async def get_user_balance(
    asset: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get balance for a specific asset."""
    balance = await user_service.get_user_balance(user_id, asset.upper())

    if not balance:
        balance = {
            "currency": asset.upper(),
            "available": 0,
            "locked": 0,
            "total": 0,
        }

    return APIResponse(success=True, data=balance)


@router.get("/trades", response_model=APIResponse)
async def get_user_trades(
    user_id: str = Depends(get_current_user_id),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    engine_type: Optional[EngineType] = Query(None, description="Filter by engine type"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """Get user's trade history."""
    trades = await user_service.get_user_trades(
        user_id,
        symbol=symbol,
        engine_type=engine_type.value if engine_type is not None else None,
        limit=limit,
    )
    return APIResponse(success=True, data=trades)


@router.get("/portfolio", response_model=APIResponse)
async def get_user_portfolio(user_id: str = Depends(get_current_user_id)):
    """Get user's portfolio summary with USDT valuation."""
    portfolio = await user_service.get_user_portfolio(user_id)
    return APIResponse(success=True, data=portfolio)
