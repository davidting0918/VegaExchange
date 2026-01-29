"""
API Key generation and management utilities for VegaExchange

Provides functions to generate, hash, and verify API keys and secrets.
"""

import secrets
from typing import Tuple

from backend.core.password import hash_password, verify_password


def generate_api_key_pair() -> Tuple[str, str]:
    """
    Generate a new API key and secret pair.
    
    Returns:
        Tuple of (api_key, api_secret) as plain text strings.
        Both are cryptographically secure random tokens.
    """
    # Generate 32-byte random tokens and encode as hex (64 characters)
    api_key = secrets.token_urlsafe(32)
    api_secret = secrets.token_urlsafe(32)
    
    return api_key, api_secret


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.
    
    Uses the same password hashing mechanism as user passwords.
    
    Args:
        api_key: Plain text API key
        
    Returns:
        Hashed API key string
    """
    return hash_password(api_key)


def hash_api_secret(api_secret: str) -> str:
    """
    Hash an API secret for secure storage.
    
    Args:
        api_secret: Plain text API secret
        
    Returns:
        Hashed API secret string
    """
    return hash_password(api_secret)


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify a plain text API key against a hashed key.
    
    Args:
        plain_key: Plain text API key to verify
        hashed_key: Hashed API key to compare against
        
    Returns:
        True if key matches, False otherwise
    """
    return verify_password(plain_key, hashed_key)


def verify_api_secret(plain_secret: str, hashed_secret: str) -> bool:
    """
    Verify a plain text API secret against a hashed secret.
    
    Args:
        plain_secret: Plain text API secret to verify
        hashed_secret: Hashed API secret to compare against
        
    Returns:
        True if secret matches, False otherwise
    """
    return verify_password(plain_secret, hashed_secret)
