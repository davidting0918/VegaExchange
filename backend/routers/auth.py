"""
Authentication API Routes

All authentication-related endpoints including registration, login, logout, and token management.
"""

import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from backend.core.api_key import get_api_key_info
from backend.core.auth import get_current_user
from backend.core.balance_utils import create_initial_balances, get_user_balances as get_user_balances_util
from backend.core.db_manager import get_db
from backend.core.id_generator import generate_user_id
from backend.core.jwt import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from backend.core.password import hash_password, verify_password
from backend.models.requests import EmailRegisterRequest, EmailLoginRequest
from backend.models.responses import APIResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleAuthRequest(BaseModel):
    """Request body for Google authentication"""
    id_token: str


async def _verify_google_token(id_token: str) -> dict:
    """
    Verify Google ID token and return user info.
    
    Args:
        id_token: The Google ID token from frontend
        
    Returns:
        Dictionary with user info (sub, email, name, picture, email_verified)
        
    Raises:
        HTTPException if token is invalid
    """
    async with httpx.AsyncClient() as client:
        # Verify token with Google's tokeninfo endpoint
        response = await client.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token}
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail="Invalid Google ID token"
            )
        
        token_info = response.json()
        
        # Verify the token is for our app (if GOOGLE_CLIENT_ID is configured)
        if GOOGLE_CLIENT_ID and token_info.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=401,
                detail="Token was not issued for this application"
            )
        
        # Check if email is verified
        if token_info.get("email_verified") != "true":
            raise HTTPException(
                status_code=401,
                detail="Email not verified by Google"
            )
        
        return {
            "google_id": token_info.get("sub"),
            "email": token_info.get("email"),
            "name": token_info.get("name", token_info.get("email", "").split("@")[0]),
            "picture": token_info.get("picture"),
        }


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


async def _create_and_store_tokens(user_id: str, include_refresh: bool = True) -> dict:
    """
    Create and store JWT tokens for a user.
    
    Returns:
        Dictionary with access_token, refresh_token, and expiration info
    """
    db = get_db()
    
    # Generate JWT tokens
    access_token = create_access_token(data={"sub": user_id, "user_id": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id, "user_id": user_id})
    
    # Store tokens in database using PostgreSQL NOW() + interval to ensure consistency
    await db.execute(
        """
        INSERT INTO access_tokens (user_id, access_token, refresh_token, expired_at, refresh_expired_at)
        VALUES (
            $1, 
            $2, 
            $3, 
            NOW() + make_interval(mins => $4),
            NOW() + make_interval(days => $5)
        )
        """,
        user_id,
        access_token,
        refresh_token,
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )
    
    result = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
    }
    
    if include_refresh:
        result["refresh_token"] = refresh_token
    
    return result


# =============================================================================
# Google OAuth Endpoints
# =============================================================================

@router.post("/google", response_model=APIResponse)
async def google_auth(request: GoogleAuthRequest):
    """
    Unified Google OAuth authentication endpoint.
    
    Handles both login and registration:
    - If user exists (by google_id) → Login
    - If user doesn't exist → Create account and Login
    
    Frontend should send the Google ID token received from Google Sign-In SDK.
    
    Returns:
        - user: User profile data
        - balances: User's token balances
        - access_token: JWT access token
        - refresh_token: JWT refresh token
        - is_new_user: Boolean indicating if this was a new registration
    """
    db = get_db()
    
    # Verify Google ID token
    google_info = await _verify_google_token(request.id_token)
    google_id = google_info["google_id"]
    email = google_info["email"]
    
    # Check if user exists by google_id
    user = await db.read_one(
        "SELECT * FROM users WHERE google_id = $1",
        google_id,
    )
    
    is_new_user = False
    
    if not user:
        # Check if email is already used by another account
        existing_email = await db.read_one(
            "SELECT user_id, google_id FROM users WHERE email = $1",
            email,
        )
        
        if existing_email:
            if existing_email.get("google_id"):
                # Another Google account with this email
                raise HTTPException(
                    status_code=400,
                    detail="Email is already associated with another Google account"
                )
            else:
                # Email account exists - link Google to existing account
                await db.execute(
                    """
                    UPDATE users 
                    SET google_id = $1, photo_url = COALESCE(photo_url, $2)
                    WHERE user_id = $3
                    """,
                    google_id,
                    google_info.get("picture"),
                    existing_email["user_id"],
                )
                user = await db.read_one(
                    "SELECT * FROM users WHERE user_id = $1",
                    existing_email["user_id"],
                )
        else:
            # Create new user
            is_new_user = True
            user_id = await _ensure_unique_user_id()
            
            user = await db.execute_returning(
                """
                INSERT INTO users (user_id, google_id, email, user_name, photo_url)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                user_id,
                google_id,
                email,
                google_info.get("name", email.split("@")[0]),
                google_info.get("picture"),
            )
            
            # Create initial balances for new user
            await create_initial_balances(user["user_id"], account_type="spot")
    
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
            "is_new_user": is_new_user,
            **token_data,
        },
    )


# =============================================================================
# Legacy Registration Endpoints (kept for backward compatibility)
# =============================================================================

@router.post("/register", response_model=APIResponse, deprecated=True)
async def register_user(
    google_id: str = Query(..., description="Google OAuth ID"),
    email: str = Query(..., description="User email"),
    display_name: Optional[str] = Query(None, description="Display name"),
    avatar_url: Optional[str] = Query(None, description="Avatar URL"),
    api_key_info: dict = Depends(get_api_key_info),
):
    """
    Register a new user via Google OAuth (called after Google OAuth).

    Creates user account with default initial balances.
    Requires both X-API-Key and X-API-Secret headers.
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

    # Get source from API key info
    source = api_key_info.get("source")

    # Create user with source
    user = await db.execute_returning(
        """
        INSERT INTO users (user_id, google_id, email, user_name, photo_url, source)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        user_id,
        google_id,
        email,
        display_name or email.split("@")[0],
        avatar_url,
        source,
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


@router.post("/register/email", response_model=APIResponse)
async def register_user_email(
    request: EmailRegisterRequest,
    api_key_info: dict = Depends(get_api_key_info),
):
    """
    Register a new user with email/password.

    Creates user account with default initial balances.
    Password must be at least 3 characters long.
    Requires both X-API-Key and X-API-Secret headers.
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

    # Get source from API key info
    source = api_key_info.get("source")

    # Create user with source
    user = await db.execute_returning(
        """
        INSERT INTO users (user_id, email, user_name, hashed_pw, source)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user_id,
        request.email,
        request.user_name or request.email.split("@")[0],
        hashed_pw,
        source,
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


@router.post("/login", response_model=APIResponse, deprecated=True)
async def login_user(
    google_id: str = Query(..., description="Google OAuth ID"),
):
    """
    [DEPRECATED] Use /api/auth/google instead.
    
    Login user via Google OAuth (called after Google OAuth verification).

    Returns user data, balances, and JWT tokens.
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


@router.post("/token", response_model=dict)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 password grant token endpoint.
    
    This endpoint follows the OAuth2 password grant flow specification.
    Used by Swagger UI and other OAuth2-compliant clients for authentication.
    
    Accepts:
    - username: User's email address
    - password: User's password
    - grant_type: Must be "password" (handled automatically by OAuth2PasswordRequestForm)
    
    Returns:
    - access_token: JWT access token
    - token_type: Always "bearer"
    - expires_in: Token expiration time in seconds
    """
    db = get_db()
    
    # OAuth2PasswordRequestForm uses 'username' field, but we use email
    email = form_data.username
    
    # Find user by email
    user = await db.read_one(
        "SELECT * FROM users WHERE email = $1",
        email,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user has password (email/password user)
    if not user.get("hashed_pw"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account was created with Google OAuth. Please use Google login instead.",
        )
    
    # Verify password
    if not verify_password(form_data.password, user["hashed_pw"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    await _update_last_login(user["user_id"])
    
    # Create and store tokens (OAuth2 standard doesn't include refresh_token in response)
    token_data = await _create_and_store_tokens(user["user_id"], include_refresh=False)
    
    return token_data


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
        SET is_active = FALSE
        WHERE user_id = $1 AND is_active = TRUE
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
    
    # Verify refresh token JWT signature and expiration
    payload = verify_token(refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired JWT token")
    
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload - missing user_id")
    
    # First, check if token exists in database (without all conditions)
    token_exists = await db.read_one(
        """
        SELECT at.is_active, at.refresh_expired_at, u.is_active as user_active
        FROM access_tokens at
        JOIN users u ON at.user_id = u.user_id
        WHERE at.refresh_token = $1
        """,
        refresh_token,
    )
    
    if not token_exists:
        raise HTTPException(status_code=401, detail="Refresh token not found in database")
    
    if not token_exists.get("is_active"):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")
    
    if not token_exists.get("user_active"):
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    # Check if database expiration has passed
    token_record = await db.read_one(
        """
        SELECT at.*, u.is_active
        FROM access_tokens at
        JOIN users u ON at.user_id = u.user_id
        WHERE at.refresh_token = $1 
          AND at.is_active = TRUE 
          AND at.refresh_expired_at > NOW()
          AND u.is_active = TRUE
        """,
        refresh_token,
    )
    
    if not token_record:
        raise HTTPException(status_code=401, detail="Refresh token expired in database")
    
    # Revoke old tokens
    await db.execute(
        """
        UPDATE access_tokens
        SET is_active = FALSE
        WHERE user_id = $1 AND is_active = TRUE
        """,
        user_id,
    )
    
    # Create and store new tokens
    token_data = await _create_and_store_tokens(user_id)
    
    return APIResponse(
        success=True,
        data=token_data,
    )
