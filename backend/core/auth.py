"""
Authentication dependencies for FastAPI routes

Provides get_current_user dependency that validates JWT tokens
and extracts user information from the token.

Supports both HTTPBearer (JWT tokens) and OAuth2PasswordBearer (OAuth2 flow)
for authentication.
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordBearer

from backend.core.db_manager import get_db
from backend.core.jwt import verify_token

# HTTP Bearer token security scheme for JWT tokens
# Enhanced with OpenAPI metadata for better documentation
security = HTTPBearer(
    scheme_name="Bearer",
    description="JWT token authentication. Use 'Bearer <token>' format in Authorization header.",
    auto_error=False,
)

# OAuth2 Password Bearer for OAuth2 password grant flow
# Used by Swagger UI and other OAuth2-compliant clients
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token",
    scheme_name="OAuth2PasswordBearer",
    description="OAuth2 password grant flow. Use this for Swagger UI authentication.",
)


async def _validate_token_and_get_user(token: str) -> dict:
    """
    Internal helper function to validate token and get user.
    
    Shared logic for both HTTPBearer and OAuth2PasswordBearer authentication.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary containing user information
        
    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    # Verify token
    payload = verify_token(token, token_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user_id from token
    user_id: Optional[str] = payload.get("sub") or payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get database connection
    db = get_db()
    
    # Verify token exists in database and is not revoked
    token_record = await db.read_one(
        """
        SELECT at.*, u.is_active
        FROM access_tokens at
        JOIN users u ON at.user_id = u.user_id
        WHERE at.access_token = $1 
          AND at.is_active = TRUE 
          AND at.expired_at > NOW()
          AND u.is_active = TRUE
        """,
        token,
    )
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not found, revoked, or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user information
    user = await db.read_one(
        "SELECT * FROM users WHERE user_id = $1 AND is_active = TRUE",
        user_id,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """
    FastAPI dependency to get current authenticated user from JWT token.
    
    Validates the JWT token from Authorization header and returns user data.
    Uses HTTPBearer security scheme for OpenAPI documentation.
    
    Args:
        credentials: HTTP Bearer token credentials from Authorization header
        
    Returns:
        Dictionary containing user information
        
    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    return await _validate_token_and_get_user(token)


async def get_current_user_oauth2(
    token: str = Depends(oauth2_scheme),
) -> dict:
    """
    FastAPI dependency to get current authenticated user from OAuth2 token.
    
    Validates the JWT token from OAuth2 password grant flow and returns user data.
    Uses OAuth2PasswordBearer security scheme for OpenAPI documentation.
    
    This is compatible with OAuth2 password grant flow used by Swagger UI.
    
    Args:
        token: OAuth2 token string from OAuth2PasswordBearer
        
    Returns:
        Dictionary containing user information
        
    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    return await _validate_token_and_get_user(token)


async def get_current_user_id(
    current_user: dict = Depends(get_current_user),
) -> str:
    """
    FastAPI dependency to get current user_id from authenticated user.
    
    This is a convenience dependency that extracts user_id from the user dict.
    
    Args:
        current_user: User dictionary from get_current_user dependency
        
    Returns:
        User ID string
    """
    return current_user["user_id"]
