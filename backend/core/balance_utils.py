"""
Balance utility functions for VegaExchange
"""

from decimal import Decimal
from typing import List, Optional

from backend.core.db_manager import get_db

# Default initial balances for new users
DEFAULT_BALANCES = {
    "USDT": Decimal("1000000"),  # 100,000 USDT
    "ORDER": Decimal("1000"),  # 1000 ORDER (for ORDER-USDT trading)
    "AMM": Decimal("1000"),  # 1000 AMM (for AMM-USDT trading)
    "VEGA": Decimal("10000"),  # 100,000,000 VEGA (for VEGA-USDT trading)
}


async def create_initial_balances(user_id: str, account_type: str = "spot") -> None:
    """
    Create initial balances for a new user.
    
    Args:
        user_id: User ID
        account_type: Account type (default: "spot")
    """
    db = get_db()
    
    for currency, amount in DEFAULT_BALANCES.items():
        await db.execute(
            """
            INSERT INTO user_balances (user_id, account_type, currency, available, locked)
            VALUES ($1, $2, $3, $4, 0)
            """,
            user_id,
            account_type,
            currency,
            amount,
        )


async def get_user_balances(user_id: str, include_total: bool = True) -> List[dict]:
    """
    Get all balances for a user.
    
    Args:
        user_id: User ID
        include_total: Whether to include total (available + locked) in the result
        
    Returns:
        List of balance dictionaries
    """
    db = get_db()
    
    if include_total:
        balances = await db.read(
            """
            SELECT currency, available, locked, (available + locked) as total
            FROM user_balances
            WHERE user_id = $1
            ORDER BY currency
            """,
            user_id,
        )
    else:
        balances = await db.read(
            """
            SELECT currency, available, locked
            FROM user_balances
            WHERE user_id = $1
            ORDER BY currency
            """,
            user_id,
        )
    
    return balances


async def get_user_balance(user_id: str, asset: str) -> Optional[dict]:
    """
    Get balance for a specific asset.
    
    Args:
        user_id: User ID
        asset: Asset currency code
        
    Returns:
        Balance dictionary or None if not found
    """
    db = get_db()
    
    balance = await db.read_one(
        """
        SELECT currency, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1 AND currency = $2
        """,
        user_id,
        asset.upper(),
    )
    
    return balance
