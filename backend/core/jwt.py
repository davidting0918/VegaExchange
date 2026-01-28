"""
JWT Token generation and validation utilities for VegaExchange

Uses python-jose for JWT token creation and verification.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Optional

from jose import JWTError, jwt

# JWT Configuration from environment variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your_super_secret_key_change_this_in_production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))


def create_access_token(data: Dict[str, str], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary containing user data (typically user_id)
        expires_delta: Optional custom expiration time. If None, uses default from config.
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, str]) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Dictionary containing user data (typically user_id)
        
    Returns:
        Encoded JWT refresh token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, str]]:
    """
    Verify and decode a JWT token.
    
    Args:
        token: JWT token string to verify
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        # Verify token type
        if payload.get("type") != token_type:
            return None
        
        return payload
    except JWTError:
        return None


def get_token_expiration_time(expires_delta: Optional[timedelta] = None) -> datetime:
    """
    Get expiration time for access token.
    
    Args:
        expires_delta: Optional custom expiration time
        
    Returns:
        Datetime object representing expiration time
    """
    if expires_delta:
        return datetime.utcnow() + expires_delta
    return datetime.utcnow() + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)


def get_refresh_token_expiration_time() -> datetime:
    """
    Get expiration time for refresh token.
    
    Returns:
        Datetime object representing expiration time
    """
    return datetime.utcnow() + timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)
