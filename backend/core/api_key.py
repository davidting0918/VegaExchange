"""
API Key authentication dependencies for FastAPI routes

Provides dependency to validate API keys from X-API-Key header.
"""

from typing import Optional

from fastapi import Depends, HTTPException, Header, status

from backend.core.api_key_manager import verify_api_key
from backend.core.db_manager import get_db


async def verify_api_key_from_header(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key", description="API Key for registration")
) -> dict:
    """
    FastAPI dependency to verify API key from X-API-Key header.
    
    Validates the API key against the database and returns key information.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        Dictionary containing API key information (api_key_id, source, etc.)
        
    Raises:
        HTTPException: If API key is missing, invalid, or inactive
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Please provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    db = get_db()
    
    # Get all active API keys to check against
    # Note: We need to check all keys because we store hashed values
    api_keys = await db.read(
        """
        SELECT api_key_id, api_key, name, source, is_active, rate_limit
        FROM api_keys
        WHERE is_active = TRUE
        """
    )
    
    if not api_keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No API keys configured",
        )
    
    # Try to match the provided key against all hashed keys
    matched_key = None
    for key_record in api_keys:
        if verify_api_key(x_api_key, key_record["api_key"]):
            matched_key = key_record
            break
    
    if not matched_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Return key information (excluding the hashed key itself)
    return {
        "api_key_id": matched_key["api_key_id"],
        "name": matched_key["name"],
        "source": matched_key["source"],
        "rate_limit": matched_key["rate_limit"],
    }


async def get_api_key_info(
    api_key_info: dict = Depends(verify_api_key_from_header)
) -> dict:
    """
    FastAPI dependency to get API key information.
    
    This is a convenience wrapper around verify_api_key_from_header.
    
    Args:
        api_key_info: API key information from verify_api_key_from_header
        
    Returns:
        Dictionary containing API key information
    """
    return api_key_info
