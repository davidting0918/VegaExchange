"""
User Information API Routes

Endpoints for retrieving current authenticated user's information, balances, trades, and portfolio.
All endpoints require authentication via JWT token.
"""

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.core.auth import get_current_user, get_current_user_id
from backend.core.balance_utils import get_user_balance as get_user_balance_util, get_user_balances as get_user_balances_util
from backend.core.db_manager import get_db
from backend.models.enums import EngineType
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("", response_model=APIResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Requires valid JWT token in Authorization header.
    """
    return APIResponse(success=True, data=current_user)


@router.get("/balances", response_model=APIResponse)
async def get_user_balances(user_id: str = Depends(get_current_user_id)):
    """
    Get all balances for the current user.
    """
    balances = await get_user_balances_util(user_id, include_total=True)
    return APIResponse(success=True, data=balances)


@router.get("/balance/{asset}", response_model=APIResponse)
async def get_user_balance(
    asset: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Get balance for a specific asset.
    """
    balance = await get_user_balance_util(user_id, asset.upper())

    if not balance:
        # Return zero balance if not found
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
    """
    Get user's trade history.
    
    Can filter by symbol and engine type.
    """
    db = get_db()

    query = """
        SELECT t.*, sc.symbol FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE t.user_id = $1
    """
    params = [user_id]
    param_idx = 2

    if symbol:
        query += f" AND sc.symbol = ${param_idx}"
        params.append(symbol.upper())
        param_idx += 1

    if engine_type is not None:
        query += f" AND t.engine_type = ${param_idx}"
        params.append(engine_type.value)
        param_idx += 1

    query += f" ORDER BY t.created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    trades = await db.read(query, *params)

    return APIResponse(success=True, data=trades)


@router.get("/portfolio", response_model=APIResponse)
async def get_user_portfolio(user_id: str = Depends(get_current_user_id)):
    """
    Get user's portfolio summary.

    Includes balances and estimated total value in USDT.
    """
    db = get_db()

    # Get balances
    balances = await get_user_balances_util(user_id, include_total=True)

    # Get prices for non-USDT assets
    # For simplicity, we'll use the latest trade price or AMM price
    prices = {"USDT": Decimal("1")}

    # Get AMM prices
    amm_prices = await db.read(
        """
        SELECT sc.base, ap.reserve_quote / ap.reserve_base as price
        FROM amm_pools ap
        JOIN symbol_configs sc USING (symbol_id)
        WHERE sc.is_active = TRUE AND ap.reserve_base > 0
        """
    )
    for p in amm_prices:
        prices[p["base"]] = Decimal(str(p["price"]))

    # Calculate total value
    total_value = Decimal("0")
    portfolio_items = []

    for balance in balances:
        currency = balance["currency"]
        total_amount = Decimal(str(balance["total"]))
        price = prices.get(currency, Decimal("0"))
        value = total_amount * price

        portfolio_items.append(
            {
                "currency": currency,
                "available": float(balance["available"]),
                "locked": float(balance["locked"]),
                "total": float(total_amount),
                "price_usdt": float(price),
                "value_usdt": float(value),
            }
        )

        total_value += value

    return APIResponse(
        success=True,
        data={
            "balances": portfolio_items,
            "total_value_usdt": float(total_value),
        },
    )
