"""
User Management API Routes

Authentication: Google OAuth and Email/Password
- Users can authenticate via Google OAuth (google_id required)
- Users can authenticate via email/password (email and password required)
- Both authentication methods are supported
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.auth import get_current_user, get_current_user_id
from backend.core.balance_utils import create_initial_balances, get_user_balance as get_user_balance_util, get_user_balances as get_user_balances_util
from backend.core.db_manager import get_db
from backend.core.id_generator import generate_user_id
from backend.core.jwt import (
    create_access_token,
    create_refresh_token,
    get_refresh_token_expiration_time,
    get_token_expiration_time,
    verify_token,
)
from backend.core.password import hash_password, verify_password
from backend.models.enums import SymbolStatus
from backend.models.requests import EmailRegisterRequest, EmailLoginRequest
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/users", tags=["users"])


# Helper functions
async def _ensure_unique_user_id() -> str:
    """Generate a unique user ID"""
    user_id = generate_user_id()
    db = get_db()
    # Ensure uniqueness (retry if collision)
    while await db.read_one("SELECT user_id FROM users WHERE user_id = $1", user_id):
        user_id = generate_user_id()
    return user_id


async def _update_last_login(user_id: str) -> None:
    """Update user's last login timestamp"""
    db = get_db()
    await db.execute(
        "UPDATE users SET last_login_at = NOW() WHERE user_id = $1",
        user_id,
    )


async def _create_and_store_tokens(user_id: str) -> dict:
    """
    Create and store JWT tokens for a user.
    
    Returns:
        Dictionary with access_token, refresh_token, and expiration info
    """
    db = get_db()
    
    # Generate JWT tokens
    access_token = create_access_token(data={"sub": user_id, "user_id": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id, "user_id": user_id})
    
    # Calculate expiration times
    access_expires_at = get_token_expiration_time()
    refresh_expires_at = get_refresh_token_expiration_time()

    # Store tokens in database
    await db.execute(
        """
        INSERT INTO access_tokens (user_id, access_token, refresh_token, expired_at, refresh_expired_at)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id,
        access_token,
        refresh_token,
        access_expires_at,
        refresh_expires_at,
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 30 * 60,  # 30 minutes in seconds
    }


@router.get("/me", response_model=APIResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Requires valid JWT token in Authorization header.
    """
    return APIResponse(success=True, data=current_user)


@router.get("/me/balances", response_model=APIResponse)
async def get_user_balances(user_id: str = Depends(get_current_user_id)):
    """
    Get all balances for the current user.
    """
    balances = await get_user_balances_util(user_id, include_total=True)
    return APIResponse(success=True, data=balances)


@router.get("/me/balance/{asset}", response_model=APIResponse)
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


@router.post("/register", response_model=APIResponse)
async def register_user(
    google_id: str = Query(..., description="Google OAuth ID"),
    email: str = Query(..., description="User email"),
    display_name: Optional[str] = Query(None, description="Display name"),
    avatar_url: Optional[str] = Query(None, description="Avatar URL"),
):
    """
    Register a new user via Google OAuth (called after Google OAuth).

    Creates user account with default initial balances.
    For email/password registration, use POST /api/users/register/email instead.
    """
    db = get_db()

    # Check if user already exists
    existing = await db.read_one(
        "SELECT user_id FROM users WHERE google_id = $1 OR email = $2",
        google_id,
        email,
    )

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Generate unique user_id
    user_id = await _ensure_unique_user_id()

    # Create user
    user = await db.execute_returning(
        """
        INSERT INTO users (user_id, google_id, email, user_name, photo_url)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user_id,
        google_id,
        email,
        display_name or email.split("@")[0],
        avatar_url,
    )

    # Create initial balances
    await create_initial_balances(user["user_id"], account_type="spot")

    # Fetch balances
    balances = await get_user_balances_util(user["user_id"], include_total=False)

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
    Login user via Google OAuth (called after Google OAuth verification).

    Returns user data, balances, and JWT tokens.
    For email/password login, use POST /api/users/login/email instead.
    """
    db = get_db()

    user = await db.read_one(
        "SELECT * FROM users WHERE google_id = $1",
        google_id,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    # Update last login
    await _update_last_login(user["user_id"])

    # Create and store tokens
    token_data = await _create_and_store_tokens(user["user_id"])

    # Get balances
    balances = await get_user_balances_util(user["user_id"], include_total=True)

    return APIResponse(
        success=True,
        data={
            "user": user,
            "balances": balances,
            **token_data,
        },
    )


@router.post("/register/email", response_model=APIResponse)
async def register_user_email(request: EmailRegisterRequest):
    """
    Register a new user with email/password.

    Creates user account with default initial balances.
    Password must be at least 3 characters long.
    """
    db = get_db()

    # Check if user already exists
    existing = await db.read_one(
        "SELECT user_id FROM users WHERE email = $1",
        request.email,
    )

    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Generate unique user_id
    user_id = await _ensure_unique_user_id()

    # Hash password
    hashed_pw = hash_password(request.password)

    # Create user
    user = await db.execute_returning(
        """
        INSERT INTO users (user_id, email, user_name, hashed_pw)
        VALUES ($1, $2, $3, $4)
        RETURNING *
        """,
        user_id,
        request.email,
        request.user_name or request.email.split("@")[0],
        hashed_pw,
    )

    # Create initial balances
    await create_initial_balances(user["user_id"], account_type="spot")

    # Fetch balances
    balances = await get_user_balances_util(user["user_id"], include_total=False)

    return APIResponse(
        success=True,
        data={
            "user": user,
            "balances": balances,
        },
    )


@router.post("/login/email", response_model=APIResponse)
async def login_user_email(request: EmailLoginRequest):
    """
    Login user with email/password.

    Returns user data, balances, and JWT tokens if credentials are valid.
    """
    db = get_db()

    # Find user by email
    user = await db.read_one(
        "SELECT * FROM users WHERE email = $1",
        request.email,
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user has password (email/password user)
    if not user.get("hashed_pw"):
        raise HTTPException(
            status_code=400,
            detail="This account was created with Google OAuth. Please use Google login instead."
        )

    # Verify password
    if not verify_password(request.password, user["hashed_pw"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last login
    await _update_last_login(user["user_id"])

    # Create and store tokens
    token_data = await _create_and_store_tokens(user["user_id"])

    # Get balances
    balances = await get_user_balances_util(user["user_id"], include_total=True)

    return APIResponse(
        success=True,
        data={
            "user": user,
            "balances": balances,
            **token_data,
        },
    )


@router.get("/me/trades", response_model=APIResponse)
async def get_user_trades(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
):
    """
    Get user's trade history across all symbols.
    """
    db = get_db()

    trades = await db.read(
        """
        SELECT t.*, sc.symbol FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE t.user_id = $1
        ORDER BY t.created_at DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )

    return APIResponse(success=True, data=trades)


@router.get("/me/portfolio", response_model=APIResponse)
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


@router.post("/logout", response_model=APIResponse)
async def logout_user(current_user: dict = Depends(get_current_user)):
    """
    Logout current user by revoking their access token.
    
    Requires valid JWT token in Authorization header.
    """
    db = get_db()
    user_id = current_user["user_id"]
    
    # Revoke all active tokens for this user
    await db.execute(
        """
        UPDATE access_tokens
        SET is_revoked = TRUE
        WHERE user_id = $1 AND is_revoked = FALSE
        """,
        user_id,
    )
    
    return APIResponse(
        success=True,
        data={"message": "Successfully logged out"},
    )


@router.post("/refresh", response_model=APIResponse)
async def refresh_token(
    refresh_token: str = Query(..., description="Refresh token"),
):
    """
    Refresh access token using refresh token.
    
    Returns new access token and refresh token.
    """
    db = get_db()
    
    # Verify refresh token
    payload = verify_token(refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    # Verify refresh token exists in database and is not revoked
    token_record = await db.read_one(
        """
        SELECT at.*, u.is_active
        FROM access_tokens at
        JOIN users u ON at.user_id = u.user_id
        WHERE at.refresh_token = $1 
          AND at.is_revoked = FALSE 
          AND at.refresh_expired_at > NOW()
          AND u.is_active = TRUE
        """,
        refresh_token,
    )
    
    if not token_record:
        raise HTTPException(status_code=401, detail="Refresh token not found, revoked, or expired")
    
    # Revoke old tokens
    await db.execute(
        """
        UPDATE access_tokens
        SET is_revoked = TRUE
        WHERE user_id = $1 AND is_revoked = FALSE
        """,
        user_id,
    )
    
    # Create and store new tokens
    token_data = await _create_and_store_tokens(user_id)
    
    return APIResponse(
        success=True,
        data=token_data,
    )
