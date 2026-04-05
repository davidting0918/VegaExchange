"""
Auth domain service — Google OAuth, email auth, JWT token management, admin auth.

All authentication business logic and DB operations live here.
Routers call these functions; they never query the DB directly.
"""

import os
from typing import Optional

import httpx
from fastapi import HTTPException, status

from backend.core.db_manager import get_db
from backend.core.id_generator import generate_admin_id, generate_user_id
from backend.core.jwt import (
    ADMIN_JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    ADMIN_JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_admin_access_token,
    create_admin_refresh_token,
    create_refresh_token,
    verify_admin_token,
    verify_token,
)
from backend.core.password import hash_password, verify_password
from backend.services.user import create_initial_balances, get_user_balances

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
ADMIN_GOOGLE_CLIENT_ID = os.getenv("ADMIN_GOOGLE_CLIENT_ID", "")
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"


# =============================================================================
# Helpers
# =============================================================================

async def _verify_google_token(id_token: str, client_id: str) -> dict:
    """
    Verify Google ID token and return user info.

    Args:
        id_token: The Google ID token from frontend
        client_id: Expected Google Client ID to validate against
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_TOKEN_INFO_URL,
            params={"id_token": id_token}
        )

        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Google ID token")

        token_info = response.json()

        if client_id and token_info.get("aud") != client_id:
            raise HTTPException(
                status_code=401,
                detail="Token was not issued for this application",
            )

        if token_info.get("email_verified") != "true":
            raise HTTPException(status_code=401, detail="Email not verified by Google")

        return {
            "google_id": token_info.get("sub"),
            "email": token_info.get("email"),
            "name": token_info.get("name", token_info.get("email", "").split("@")[0]),
            "picture": token_info.get("picture"),
        }


async def _ensure_unique_user_id() -> str:
    """Generate a unique user ID."""
    user_id = generate_user_id()
    db = get_db()
    while await db.read_one("SELECT user_id FROM users WHERE user_id = $1", user_id):
        user_id = generate_user_id()
    return user_id


async def _ensure_unique_admin_id() -> str:
    """Generate a unique admin ID (6-char alphanumeric)."""
    admin_id = generate_admin_id()
    db = get_db()
    while await db.read_one("SELECT admin_id FROM admins WHERE admin_id = $1", admin_id):
        admin_id = generate_admin_id()
    return admin_id


async def _update_last_login(user_id: str) -> None:
    """Update user's last login timestamp."""
    db = get_db()
    await db.execute(
        "UPDATE users SET last_login_at = NOW() WHERE user_id = $1",
        user_id,
    )


async def _create_and_store_tokens(user_id: str, include_refresh: bool = True) -> dict:
    """Create and store JWT tokens for a user."""
    db = get_db()

    access_token = create_access_token(data={"sub": user_id, "user_id": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id, "user_id": user_id})

    await db.execute(
        """
        INSERT INTO access_tokens (user_id, access_token, refresh_token, expired_at, refresh_expired_at)
        VALUES (
            $1, $2, $3,
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
        "expires_in": JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

    if include_refresh:
        result["refresh_token"] = refresh_token

    return result


async def _create_and_store_admin_tokens(admin_id: str) -> dict:
    """Create and store JWT tokens for an admin in admin_access_tokens table."""
    db = get_db()

    access_token = create_admin_access_token(data={"sub": admin_id, "admin_id": admin_id})
    refresh_token = create_admin_refresh_token(data={"sub": admin_id, "admin_id": admin_id})

    await db.execute(
        """
        INSERT INTO admin_access_tokens (admin_id, access_token, refresh_token, expired_at, refresh_expired_at)
        VALUES (
            $1, $2, $3,
            NOW() + make_interval(mins => $4),
            NOW() + make_interval(days => $5)
        )
        """,
        admin_id,
        access_token,
        refresh_token,
        ADMIN_JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        ADMIN_JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ADMIN_JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# =============================================================================
# Exchange User Auth
# =============================================================================

async def google_auth(id_token: str) -> dict:
    """
    Unified Google OAuth login/register for exchange users.

    Returns dict with user, balances, tokens, is_new_user.
    """
    db = get_db()

    google_info = await _verify_google_token(id_token, GOOGLE_CLIENT_ID)
    google_id = google_info["google_id"]
    email = google_info["email"]

    user = await db.read_one("SELECT * FROM users WHERE google_id = $1", google_id)

    is_new_user = False

    if not user:
        existing_email = await db.read_one(
            "SELECT user_id, google_id FROM users WHERE email = $1", email
        )

        if existing_email:
            if existing_email.get("google_id"):
                raise HTTPException(
                    status_code=400,
                    detail="Email is already associated with another Google account"
                )
            else:
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
                    "SELECT * FROM users WHERE user_id = $1", existing_email["user_id"]
                )
        else:
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

            await create_initial_balances(user["user_id"], account_type="spot")

    await _update_last_login(user["user_id"])
    token_data = await _create_and_store_tokens(user["user_id"])
    balances = await get_user_balances(user["user_id"], include_total=True)

    return {
        "user": user,
        "balances": balances,
        "is_new_user": is_new_user,
        **token_data,
    }


async def register_legacy(
    google_id: str, email: str, display_name: Optional[str],
    avatar_url: Optional[str], source: Optional[str],
) -> dict:
    """Legacy Google registration (deprecated)."""
    db = get_db()

    existing = await db.read_one(
        "SELECT user_id FROM users WHERE google_id = $1 OR email = $2",
        google_id, email,
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    user_id = await _ensure_unique_user_id()

    user = await db.execute_returning(
        """
        INSERT INTO users (user_id, google_id, email, user_name, photo_url, source)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING *
        """,
        user_id, google_id, email,
        display_name or email.split("@")[0],
        avatar_url, source,
    )

    await create_initial_balances(user["user_id"], account_type="spot")
    balances = await get_user_balances(user["user_id"], include_total=False)

    return {"user": user, "balances": balances}


async def register_email(
    email: str, password: str, user_name: Optional[str], source: Optional[str],
) -> dict:
    """Register a new user with email/password."""
    db = get_db()

    existing = await db.read_one("SELECT user_id FROM users WHERE email = $1", email)
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user_id = await _ensure_unique_user_id()
    hashed_pw = hash_password(password)

    user = await db.execute_returning(
        """
        INSERT INTO users (user_id, email, user_name, hashed_pw, source)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user_id, email, user_name or email.split("@")[0], hashed_pw, source,
    )

    await create_initial_balances(user["user_id"], account_type="spot")
    balances = await get_user_balances(user["user_id"], include_total=False)

    return {"user": user, "balances": balances}


async def login_email(email: str, password: str) -> dict:
    """Login user with email/password."""
    db = get_db()

    user = await db.read_one("SELECT * FROM users WHERE email = $1", email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.get("hashed_pw"):
        raise HTTPException(
            status_code=400,
            detail="This account was created with Google OAuth. Please use Google login instead."
        )

    if not verify_password(password, user["hashed_pw"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    await _update_last_login(user["user_id"])
    token_data = await _create_and_store_tokens(user["user_id"])
    balances = await get_user_balances(user["user_id"], include_total=True)

    return {"user": user, "balances": balances, **token_data}


async def login_legacy(google_id: str) -> dict:
    """Legacy Google login (deprecated)."""
    db = get_db()

    user = await db.read_one("SELECT * FROM users WHERE google_id = $1", google_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please register first.")

    await _update_last_login(user["user_id"])
    token_data = await _create_and_store_tokens(user["user_id"])
    balances = await get_user_balances(user["user_id"], include_total=True)

    return {"user": user, "balances": balances, **token_data}


async def login_oauth2_password(email: str, password: str) -> dict:
    """OAuth2 password grant flow for Swagger UI."""
    db = get_db()

    user = await db.read_one("SELECT * FROM users WHERE email = $1", email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("hashed_pw"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account was created with Google OAuth. Please use Google login instead.",
        )

    if not verify_password(password, user["hashed_pw"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await _update_last_login(user["user_id"])
    return await _create_and_store_tokens(user["user_id"], include_refresh=False)


async def logout_user(user_id: str) -> None:
    """Revoke all active tokens for a user."""
    db = get_db()
    await db.execute(
        "UPDATE access_tokens SET is_active = FALSE WHERE user_id = $1 AND is_active = TRUE",
        user_id,
    )


async def refresh_user_token(refresh_token: str) -> dict:
    """Refresh access token using refresh token."""
    db = get_db()

    payload = verify_token(refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired JWT token")

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload - missing user_id")

    # Check token exists
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

    # Validate expiration
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

    # Revoke old, create new
    await db.execute(
        "UPDATE access_tokens SET is_active = FALSE WHERE user_id = $1 AND is_active = TRUE",
        user_id,
    )

    return await _create_and_store_tokens(user_id)


# =============================================================================
# Admin Auth
# =============================================================================

async def admin_google_auth(id_token: str) -> dict:
    """
    Admin Google OAuth login. Completely independent from exchange user auth.

    Validates against ADMIN_GOOGLE_CLIENT_ID, checks admin_whitelist,
    creates/updates admin in admins table, stores tokens in admin_access_tokens.
    """
    db = get_db()

    google_info = await _verify_google_token(id_token, ADMIN_GOOGLE_CLIENT_ID)
    google_id = google_info["google_id"]
    email = google_info["email"]

    # Check whitelist
    whitelist_entry = await db.read_one(
        "SELECT id FROM admin_whitelist WHERE email = $1", email
    )
    if not whitelist_entry:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not in the admin whitelist",
        )

    # Find or create admin
    admin = await db.read_one("SELECT * FROM admins WHERE google_id = $1", google_id)
    is_new_admin = False

    if not admin:
        admin = await db.read_one("SELECT * FROM admins WHERE email = $1", email)

        if admin:
            await db.execute(
                "UPDATE admins SET google_id = $1, photo_url = COALESCE(photo_url, $2) WHERE admin_id = $3",
                google_id, google_info.get("picture"), admin["admin_id"],
            )
            admin = await db.read_one("SELECT * FROM admins WHERE admin_id = $1", admin["admin_id"])
        else:
            is_new_admin = True
            admin_id = await _ensure_unique_admin_id()

            admin = await db.execute_returning(
                """
                INSERT INTO admins (admin_id, google_id, email, name, photo_url)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                admin_id, google_id, email,
                google_info.get("name", email.split("@")[0]),
                google_info.get("picture"),
            )

    if not admin.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled",
        )

    await db.execute(
        "UPDATE admins SET last_login_at = NOW() WHERE admin_id = $1",
        admin["admin_id"],
    )

    token_data = await _create_and_store_admin_tokens(admin["admin_id"])

    return {
        "admin": {
            "admin_id": admin["admin_id"],
            "email": admin["email"],
            "name": admin["name"],
            "photo_url": admin.get("photo_url"),
            "role": admin.get("role", "admin"),
        },
        "is_new_admin": is_new_admin,
        **token_data,
    }


async def refresh_admin_token(refresh_token: str) -> dict:
    """Refresh admin access token."""
    db = get_db()

    payload = verify_admin_token(refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired admin refresh token")

    admin_id = payload.get("sub") or payload.get("admin_id")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Invalid admin token payload")

    token_record = await db.read_one(
        """
        SELECT aat.*, a.is_active as admin_active
        FROM admin_access_tokens aat
        JOIN admins a ON aat.admin_id = a.admin_id
        WHERE aat.refresh_token = $1
          AND aat.is_active = TRUE
          AND aat.refresh_expired_at > NOW()
          AND a.is_active = TRUE
        """,
        refresh_token,
    )

    if not token_record:
        raise HTTPException(status_code=401, detail="Admin refresh token not found, revoked, or expired")

    await db.execute(
        "UPDATE admin_access_tokens SET is_active = FALSE WHERE admin_id = $1 AND is_active = TRUE",
        admin_id,
    )

    return await _create_and_store_admin_tokens(admin_id)


async def logout_admin(admin_id: str) -> None:
    """Revoke all active admin tokens."""
    db = get_db()
    await db.execute(
        "UPDATE admin_access_tokens SET is_active = FALSE WHERE admin_id = $1 AND is_active = TRUE",
        admin_id,
    )
