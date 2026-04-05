"""
Authentication API Routes

Thin router — delegates all business logic to services/auth.py.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import OAuth2PasswordRequestForm

from backend.core.auth import get_current_user, require_admin
from backend.models.auth import (
    AdminGoogleAuthRequest,
    EmailLoginRequest,
    EmailRegisterRequest,
    GoogleAuthRequest,
)
from backend.models.common import APIResponse
from backend.services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["authentication"])


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
    """
    result = await auth_service.google_auth(request.id_token)
    return APIResponse(success=True, data=result)


# =============================================================================
# Legacy Registration Endpoints (kept for backward compatibility)
# =============================================================================

@router.post("/register", response_model=APIResponse, deprecated=True)
async def register_user(
    google_id: str = Query(..., description="Google OAuth ID"),
    email: str = Query(..., description="User email"),
    display_name: Optional[str] = Query(None, description="Display name"),
    avatar_url: Optional[str] = Query(None, description="Avatar URL"),
):
    """[DEPRECATED] Register a new user via Google OAuth."""
    result = await auth_service.register_legacy(
        google_id=google_id,
        email=email,
        display_name=display_name,
        avatar_url=avatar_url,
    )
    return APIResponse(success=True, data=result)


@router.post("/register/email", response_model=APIResponse)
async def register_user_email(request: EmailRegisterRequest):
    """Register a new user with email/password."""
    result = await auth_service.register_email(
        email=request.email,
        password=request.password,
        user_name=request.user_name,
    )
    return APIResponse(success=True, data=result)


@router.post("/login", response_model=APIResponse, deprecated=True)
async def login_user(
    google_id: str = Query(..., description="Google OAuth ID"),
):
    """[DEPRECATED] Use /api/auth/google instead."""
    result = await auth_service.login_legacy(google_id)
    return APIResponse(success=True, data=result)


@router.post("/login/email", response_model=APIResponse)
async def login_user_email(request: EmailLoginRequest):
    """Login user with email/password."""
    result = await auth_service.login_email(request.email, request.password)
    return APIResponse(success=True, data=result)


@router.post("/token", response_model=dict)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 password grant token endpoint.

    Used by Swagger UI and other OAuth2-compliant clients.
    """
    return await auth_service.login_oauth2_password(
        email=form_data.username,
        password=form_data.password,
    )


@router.post("/logout", response_model=APIResponse)
async def logout_user(current_user: dict = Depends(get_current_user)):
    """Logout current user by revoking their access token."""
    await auth_service.logout_user(current_user["user_id"])
    return APIResponse(success=True, data={"message": "Successfully logged out"})


@router.post("/refresh", response_model=APIResponse)
async def refresh_token(
    refresh_token: str = Query(..., description="Refresh token"),
):
    """Refresh access token using refresh token."""
    result = await auth_service.refresh_user_token(refresh_token)
    return APIResponse(success=True, data=result)


# =============================================================================
# Admin Authentication Endpoints
# =============================================================================

@router.post("/admin/google", response_model=APIResponse)
async def admin_google_auth(request: AdminGoogleAuthRequest):
    """
    Admin Google OAuth authentication endpoint.

    Validates against admin whitelist. Completely independent from exchange user auth.
    """
    result = await auth_service.admin_google_auth(request.id_token)
    return APIResponse(success=True, data=result)


@router.post("/admin/refresh", response_model=APIResponse)
async def admin_refresh_token(
    refresh_token: str = Query(..., description="Admin refresh token"),
):
    """Refresh admin access token using admin refresh token."""
    result = await auth_service.refresh_admin_token(refresh_token)
    return APIResponse(success=True, data=result)


@router.post("/admin/logout", response_model=APIResponse)
async def admin_logout(current_admin: dict = Depends(require_admin)):
    """Logout admin by revoking all active admin tokens."""
    await auth_service.logout_admin(current_admin["admin_id"])
    return APIResponse(success=True, data={"message": "Admin successfully logged out"})
