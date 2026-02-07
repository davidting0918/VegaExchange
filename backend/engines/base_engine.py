"""
Base engine interface for all trading engines
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.core.id_generator import generate_trade_id
from backend.models.enums import EngineType, OrderSide, TradeStatus


@dataclass
class TradeResult:
    """Result of a trade execution"""

    success: bool
    trade_id: Optional[str] = None
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    engine_type: EngineType = EngineType.AMM
    price: Decimal = Decimal("0")
    quantity: Decimal = Decimal("0")
    quote_amount: Decimal = Decimal("0")
    fee_amount: Decimal = Decimal("0")
    fee_asset: str = ""
    status: TradeStatus = TradeStatus.COMPLETED
    engine_data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    # For CLOB: order information
    order_id: Optional[str] = None
    fills: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QuoteResult:
    """Result of a quote request (preview without execution)"""

    success: bool
    input_amount: Decimal = Decimal("0")
    input_asset: str = ""
    output_amount: Decimal = Decimal("0")
    output_asset: str = ""
    effective_price: Decimal = Decimal("0")
    price_impact: Optional[Decimal] = None
    fee_amount: Decimal = Decimal("0")
    fee_asset: str = ""
    slippage: Optional[Decimal] = None
    error_message: Optional[str] = None


class BaseEngine(ABC):
    """
    Abstract base class for all trading engines.

    All engines must implement these methods to ensure
    consistent behavior across different market mechanisms.
    """

    def __init__(self, db_client, symbol_config: Dict[str, Any]):
        """
        Initialize engine with database client and symbol configuration.

        Args:
            db_client: PostgreSQL async client
            symbol_config: Symbol configuration dictionary from database
        """
        self.db = db_client
        self.symbol_config = symbol_config
        self.symbol = symbol_config["symbol"]
        self.base_asset = symbol_config["base"]
        self.quote_asset = symbol_config["quote"]
        self.engine_params = symbol_config.get("engine_params", {})

    @property
    @abstractmethod
    def engine_type(self) -> EngineType:
        """Return the engine type"""
        pass

    @abstractmethod
    async def execute_trade(
        self,
        user_id: str,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        **kwargs,
    ) -> TradeResult:
        """
        Execute a trade.

        Args:
            user_id: User placing the trade
            side: Buy or sell
            quantity: Amount of base asset (optional)
            quote_amount: Amount of quote asset (optional)
            price: Limit price (for CLOB limit orders)
            **kwargs: Engine-specific parameters

        Returns:
            TradeResult with execution details
        """
        pass

    @abstractmethod
    async def get_quote(
        self,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        **kwargs,
    ) -> QuoteResult:
        """
        Get a quote for a potential trade (preview without execution).

        Args:
            side: Buy or sell
            quantity: Amount of base asset (optional)
            quote_amount: Amount of quote asset (optional)
            **kwargs: Engine-specific parameters

        Returns:
            QuoteResult with estimated execution details
        """
        pass

    @abstractmethod
    async def get_market_data(self) -> Dict[str, Any]:
        """
        Get current market data for the symbol.

        Returns:
            Dictionary with price, volume, and engine-specific data
        """
        pass

    async def validate_balance(
        self,
        user_id: str,
        asset: str,
        required_amount: Decimal,
    ) -> bool:
        """
        Check if user has sufficient balance for a trade (spot account).

        Args:
            user_id: User ID
            asset: Asset to check
            required_amount: Amount needed

        Returns:
            True if user has sufficient available balance
        """
        balance = await self.db.read_one(
            """
            SELECT available FROM user_balances
            WHERE user_id = $1 AND account_type = 'spot' AND currency = $2
            """,
            user_id,
            asset,
        )

        if not balance:
            return False

        return Decimal(str(balance["available"])) >= required_amount

    async def update_balance(
        self,
        user_id: str,
        asset: str,
        available_delta: Decimal,
        locked_delta: Decimal = Decimal("0"),
    ) -> bool:
        """
        Update user's balance for an asset (spot account only).

        Args:
            user_id: User ID
            asset: Asset to update
            available_delta: Change in available balance (can be negative)
            locked_delta: Change in locked balance (can be negative)

        Returns:
            True if exactly one row was updated
        """
        result = await self.db.execute(
            """
            UPDATE user_balances
            SET available = available + $3,
                locked = locked + $4,
                balance = (available + $3) + (locked + $4),
                updated_at = NOW()
            WHERE user_id = $1 AND account_type = 'spot' AND currency = $2
            AND available + $3 >= 0
            AND locked + $4 >= 0
            """,
            user_id,
            asset,
            available_delta,
            locked_delta,
        )

        # Require exactly one row updated (avoid "UPDATE 1" in "UPDATE 2" false positive)
        return result.strip() == "UPDATE 1"

    async def ensure_balance_exists(
        self,
        user_id: str,
        asset: str,
        account_type: str = "spot",
        initial_amount: Decimal = Decimal("0"),
    ) -> bool:
        """
        Ensure a balance entry exists for a user and asset.
        Creates the balance if it doesn't exist, otherwise does nothing.

        Args:
            user_id: User ID
            asset: Asset currency code
            account_type: Account type (default: "spot")
            initial_amount: Initial available balance if creating new entry (default: 0)

        Returns:
            True if balance exists or was created successfully
        """
        result = await self.db.execute(
            """
            INSERT INTO user_balances (user_id, account_type, currency, available, locked)
            VALUES ($1, $2, $3, $4, 0)
            ON CONFLICT (account_type, user_id, currency) DO NOTHING
            """,
            user_id,
            account_type,
            asset,
            initial_amount,
        )

        # INSERT returns empty string if conflict (balance already exists)
        # or "INSERT 0 1" if new balance was created
        return True

    async def record_trade(
        self,
        user_id: str,
        side: OrderSide,
        price: Decimal,
        quantity: Decimal,
        quote_amount: Decimal,
        fee_amount: Decimal,
        fee_asset: str,
        status: TradeStatus = TradeStatus.COMPLETED,
        engine_data: Optional[Dict[str, Any]] = None,
        counterparty_user_id: Optional[str] = None,
    ) -> str:
        """
        Record a trade in the database.

        Returns:
            Trade ID
        """
        # Generate trade ID
        trade_id = generate_trade_id()

        result = await self.db.execute_returning(
            """
            INSERT INTO trades (
                trade_id, symbol_id, user_id, side, engine_type,
                price, quantity, quote_amount,
                fee_amount, fee_asset, status, engine_data,
                counterparty
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13
            )
            RETURNING trade_id
            """,
            trade_id,
            self.symbol_config["symbol_id"],
            user_id,
            side.value,
            self.engine_type.value,
            price,
            quantity,
            quote_amount,
            fee_amount,
            fee_asset,
            status.value,
            json.dumps(engine_data) if engine_data else "{}",
            counterparty_user_id,  # Maps to counterparty column (NULL for AMM trades)
        )

        return result["trade_id"]
