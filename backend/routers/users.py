"""
User Management API Routes

Authentication: Google OAuth only
- Users must authenticate via Google OAuth
- google_id is required for registration and login
- No email/password authentication supported
"""

from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.db_manager import get_db
from backend.models.responses import APIResponse, BalanceResponse

router = APIRouter(prefix="/api/users", tags=["users"])


# Default initial balances for new users
DEFAULT_BALANCES = {
    "USDT": Decimal("100000"),  # 100,000 USDT
    "BTC": Decimal("1"),  # 1 BTC
    "ETH": Decimal("10"),  # 10 ETH
    "SOL": Decimal("100"),  # 100 SOL
    "ORDER": Decimal("1000"),  # 1000 ORDER (for ORDER-USDT trading)
    "AMM": Decimal("1000"),  # 1000 AMM (for AMM-USDT trading)
}


@router.get("/me", response_model=APIResponse)
async def get_current_user(user_id: UUID = Query(..., description="User ID")):
    """
    Get current user information.

    In production, user_id would come from JWT token.
    """
    db = get_db()

    user = await db.read_one(
        "SELECT * FROM users WHERE id = $1",
        user_id,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return APIResponse(success=True, data=user)


@router.get("/me/balances", response_model=APIResponse)
async def get_user_balances(user_id: UUID = Query(..., description="User ID")):
    """
    Get all balances for the current user.
    """
    db = get_db()

    balances = await db.read(
        """
        SELECT asset, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1
        ORDER BY asset
        """,
        user_id,
    )

    return APIResponse(success=True, data=balances)


@router.get("/me/balance/{asset}", response_model=APIResponse)
async def get_user_balance(
    asset: str,
    user_id: UUID = Query(..., description="User ID"),
):
    """
    Get balance for a specific asset.
    """
    db = get_db()

    balance = await db.read_one(
        """
        SELECT asset, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1 AND asset = $2
        """,
        user_id,
        asset.upper(),
    )

    if not balance:
        # Return zero balance if not found
        balance = {
            "asset": asset.upper(),
            "available": 0,
            "locked": 0,
            "total": 0,
        }

    return APIResponse(success=True, data=balance)


@router.post("/register", response_model=APIResponse)
async def register_user(
    google_id: str = Query(..., description="Google OAuth ID"),
    email: str = Query(..., description="User email"),
    display_name: Optional[str] = Query(None, description="Display name"),
    avatar_url: Optional[str] = Query(None, description="Avatar URL"),
):
    """
    Register a new user (called after Google OAuth).

    Creates user account with default initial balances.
    """
    db = get_db()

    # Check if user already exists
    existing = await db.read_one(
        "SELECT id FROM users WHERE google_id = $1 OR email = $2",
        google_id,
        email,
    )

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user
    user = await db.execute_returning(
        """
        INSERT INTO users (google_id, email, display_name, avatar_url)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        google_id,
        email,
        display_name,
        avatar_url,
    )

    # Create initial balances
    for asset, amount in DEFAULT_BALANCES.items():
        await db.execute(
            """
            INSERT INTO user_balances (user_id, asset, available, locked)
            VALUES ($1, $2, $3, 0)
            """,
            user["id"],
            asset,
            amount,
        )

    # Fetch balances
    balances = await db.read(
        "SELECT asset, available, locked FROM user_balances WHERE user_id = $1",
        user["id"],
    )

    return APIResponse(
        success=True,
        data={
            "user": user,
            "balances": balances,
        },
    )


@router.post("/login", response_model=APIResponse)
async def login_user(
    google_id: str = Query(..., description="Google OAuth ID"),
):
    """
    Login user (called after Google OAuth verification).

    Returns user data if exists, or creates new account.
    """
    db = get_db()

    user = await db.read_one(
        "SELECT * FROM users WHERE google_id = $1",
        google_id,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    # Update last login
    await db.execute(
        "UPDATE users SET last_login_at = NOW() WHERE id = $1",
        user["id"],
    )

    # Get balances
    balances = await db.read(
        """
        SELECT asset, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1
        """,
        user["id"],
    )

    return APIResponse(
        success=True,
        data={
            "user": user,
            "balances": balances,
        },
    )


@router.get("/me/trades", response_model=APIResponse)
async def get_user_trades(
    user_id: UUID = Query(..., description="User ID"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get user's trade history across all symbols.
    """
    db = get_db()

    trades = await db.read(
        """
        SELECT t.*, sc.symbol FROM trades t
        JOIN symbol_configs sc ON t.symbol_config_id = sc.id
        WHERE t.user_id = $1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    return APIResponse(success=True, data=trades)


@router.get("/me/portfolio", response_model=APIResponse)
async def get_user_portfolio(user_id: UUID = Query(..., description="User ID")):
    """
    Get user's portfolio summary.

    Includes balances and estimated total value in USDT.
    """
    db = get_db()

    # Get balances
    balances = await db.read(
        """
        SELECT asset, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1
        """,
        user_id,
    )

    # Get prices for non-USDT assets
    # For simplicity, we'll use the latest trade price or AMM price
    prices = {"USDT": Decimal("1")}

    # Get AMM prices
    amm_prices = await db.read(
        """
        SELECT sc.base_asset, ap.reserve_quote / ap.reserve_base as price
        FROM amm_pools ap
        JOIN symbol_configs sc ON ap.symbol_config_id = sc.id
        WHERE sc.status = 'active' AND ap.reserve_base > 0
        """
    )
    for p in amm_prices:
        prices[p["base_asset"]] = Decimal(str(p["price"]))

    # Calculate total value
    total_value = Decimal("0")
    portfolio_items = []

    for balance in balances:
        asset = balance["asset"]
        total_amount = Decimal(str(balance["total"]))
        price = prices.get(asset, Decimal("0"))
        value = total_amount * price

        portfolio_items.append(
            {
                "asset": asset,
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
