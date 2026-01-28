"""
ID Generator for VegaExchange

Different ID generation strategies for different entity types.
"""

import hashlib
import secrets
import time


def generate_user_id() -> str:
    """
    Generate a 6-digit random integer user ID.
    
    Returns:
        6-digit random integer as string (e.g., "123456")
    """
    # Generate random 6-digit number (100000 to 999999)
    return str(secrets.randbelow(900000) + 100000)


def generate_pool_id() -> str:
    """
    Generate a pool ID similar to crypto address (0x prefix).
    
    Uses hash-based generation similar to Ethereum addresses.
    Format: 0x + 40 hex characters (20 bytes)
    
    Returns:
        Pool ID string (e.g., "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
    """
    # Generate random bytes and hash them
    random_bytes = secrets.token_bytes(20)
    # Convert to hex and add 0x prefix
    return "0x" + random_bytes.hex()


def generate_order_id() -> str:
    """
    Generate order ID using 13-digit timestamp (milliseconds since epoch).
    
    Returns:
        13-digit timestamp as string (e.g., "1704067200000")
    """
    # Get current time in milliseconds
    return str(int(time.time() * 1000))


def generate_trade_id() -> str:
    """
    Generate trade ID using 13-digit timestamp (milliseconds since epoch).
    
    Returns:
        13-digit timestamp as string (e.g., "1704067200000")
    """
    # Get current time in milliseconds
    return str(int(time.time() * 1000))


# Note: symbol_configs and lp_positions use SERIAL (auto-increment)
# These are handled by the database, no generator needed
