"""
User domain service — user info, balances, portfolio, trade history.

All DB operations for the user domain live here.
Routers call these functions; they never query the DB directly.
"""

from decimal import Decimal
from typing import List, Optional

from backend.core.db_manager import get_db

# Default initial balances for new users (fallback if platform_settings not available)
DEFAULT_BALANCES = {
    "USDT": Decimal("1000000"),
    "ORDER": Decimal("1000"),
    "AMM": Decimal("1000"),
    "VEGA": Decimal("10000"),
}


async def create_initial_balances(user_id: str, account_type: str = "spot") -> None:
    """Create initial balances for a new user."""
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
    """Get all balances for a user."""
    db = get_db()

    if include_total:
        balances = await db.read(
            """
            SELECT currency, available, locked, (available + locked) as total
            FROM user_balances
            WHERE user_id = $1 AND account_type = 'spot'
            ORDER BY currency
            """,
            user_id,
        )
    else:
        balances = await db.read(
            """
            SELECT currency, available, locked
            FROM user_balances
            WHERE user_id = $1 AND account_type = 'spot'
            ORDER BY currency
            """,
            user_id,
        )

    return balances


async def get_user_balance(user_id: str, asset: str) -> Optional[dict]:
    """Get balance for a specific asset."""
    db = get_db()

    balance = await db.read_one(
        """
        SELECT currency, available, locked, (available + locked) as total
        FROM user_balances
        WHERE user_id = $1 AND account_type = 'spot' AND currency = $2
        """,
        user_id,
        asset.upper(),
    )

    return balance


async def get_user_trades(
    user_id: str,
    symbol: Optional[str] = None,
    engine_type: Optional[int] = None,
    limit: int = 50,
) -> List[dict]:
    """Get user's trade history with optional filters."""
    db = get_db()

    query = """
        SELECT t.*, sc.symbol FROM trades t
        JOIN symbol_configs sc USING (symbol_id)
        WHERE t.user_id = $1
    """
    params: list = [user_id]
    param_idx = 2

    if symbol:
        query += f" AND sc.symbol = ${param_idx}"
        params.append(symbol.upper())
        param_idx += 1

    if engine_type is not None:
        query += f" AND t.engine_type = ${param_idx}"
        params.append(engine_type)
        param_idx += 1

    query += f" ORDER BY t.created_at DESC LIMIT ${param_idx}"
    params.append(limit)

    return await db.read(query, *params)


async def get_user_portfolio(user_id: str) -> dict:
    """
    Get user's portfolio summary with USDT valuation.

    Calculates total value using AMM pool prices for non-USDT assets.
    """
    db = get_db()

    balances = await get_user_balances(user_id, include_total=True)

    # Get prices for non-USDT assets from AMM pools
    prices = {"USDT": Decimal("1")}

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

    return {
        "balances": portfolio_items,
        "total_value_usdt": float(total_value),
    }
