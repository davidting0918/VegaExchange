"""
Engine Router - Routes trades to the correct engine based on symbol configuration
"""

from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import UUID

from backend.engines.amm_engine import AMMEngine
from backend.engines.base_engine import BaseEngine, QuoteResult, TradeResult
from backend.engines.clob_engine import CLOBEngine
from backend.models.enums import EngineType, OrderSide, OrderType


class EngineRouter:
    """
    Routes trading operations to the correct engine based on symbol configuration.

    This is the central dispatcher that:
    1. Looks up the symbol's engine type
    2. Instantiates the appropriate engine
    3. Delegates the operation to that engine
    """

    def __init__(self, db_client):
        """
        Initialize the router with database client.

        Args:
            db_client: PostgreSQL async client
        """
        self.db = db_client
        self._engine_cache: Dict[str, BaseEngine] = {}

    async def _get_symbol_config(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol configuration from database"""
        return await self.db.read_one(
            """
            SELECT * FROM symbol_configs
            WHERE symbol = $1 AND status = 'active'
            """,
            symbol.upper(),
        )

    async def _get_engine(self, symbol: str) -> Optional[BaseEngine]:
        """
        Get or create the appropriate engine for a symbol.

        Uses caching to avoid recreating engines for each request.
        """
        symbol = symbol.upper()

        # Check cache first
        if symbol in self._engine_cache:
            return self._engine_cache[symbol]

        # Get symbol config
        config = await self._get_symbol_config(symbol)
        if not config:
            return None

        # Create appropriate engine based on type
        engine_type = EngineType(config["engine_type"])

        if engine_type == EngineType.AMM:
            engine = AMMEngine(self.db, config)
        elif engine_type == EngineType.CLOB:
            engine = CLOBEngine(self.db, config)
        else:
            return None

        # Cache the engine
        self._engine_cache[symbol] = engine
        return engine

    def invalidate_cache(self, symbol: Optional[str] = None):
        """
        Invalidate engine cache.

        Args:
            symbol: Specific symbol to invalidate, or None to clear all
        """
        if symbol:
            self._engine_cache.pop(symbol.upper(), None)
        else:
            self._engine_cache.clear()

    async def execute_trade(
        self,
        user_id: UUID,
        symbol: str,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        order_type: Optional[OrderType] = None,
        **kwargs,
    ) -> TradeResult:
        """
        Execute a trade on the appropriate engine.

        This is the unified trade endpoint that routes to the correct engine.
        """
        engine = await self._get_engine(symbol)

        if not engine:
            return TradeResult(
                success=False,
                error_message=f"Symbol '{symbol}' not found or not active",
            )

        # Route to the appropriate execute method
        if engine.engine_type == EngineType.AMM:
            return await engine.execute_trade(
                user_id=user_id,
                side=side,
                quantity=quantity,
                quote_amount=quote_amount,
                **kwargs,
            )
        elif engine.engine_type == EngineType.CLOB:
            return await engine.execute_trade(
                user_id=user_id,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type or OrderType.LIMIT,
                **kwargs,
            )
        else:
            return TradeResult(
                success=False,
                error_message=f"Unsupported engine type: {engine.engine_type}",
            )

    async def get_quote(
        self,
        symbol: str,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        **kwargs,
    ) -> QuoteResult:
        """Get a quote for a potential trade"""
        engine = await self._get_engine(symbol)

        if not engine:
            return QuoteResult(
                success=False,
                error_message=f"Symbol '{symbol}' not found or not active",
            )

        return await engine.get_quote(
            side=side,
            quantity=quantity,
            quote_amount=quote_amount,
            **kwargs,
        )

    async def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get market data for a symbol"""
        engine = await self._get_engine(symbol)

        if not engine:
            return {"error": f"Symbol '{symbol}' not found or not active"}

        return await engine.get_market_data()

    async def get_all_symbols(self) -> list[Dict[str, Any]]:
        """Get all active symbols with their configurations"""
        return await self.db.read(
            """
            SELECT * FROM symbol_configs
            WHERE status = 'active'
            ORDER BY symbol
            """
        )

    async def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a symbol"""
        config = await self._get_symbol_config(symbol)
        if not config:
            return None

        market_data = await self.get_market_data(symbol)

        return {
            **config,
            "market_data": market_data,
        }


# Singleton instance factory
_router_instance: Optional[EngineRouter] = None


def get_engine_router(db_client) -> EngineRouter:
    """Get or create the engine router singleton"""
    global _router_instance
    if _router_instance is None:
        _router_instance = EngineRouter(db_client)
    return _router_instance
