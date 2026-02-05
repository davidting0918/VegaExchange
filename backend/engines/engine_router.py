"""
Engine Router - Routes trades to the correct engine based on symbol configuration
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.engines.amm_engine import AMMEngine
from backend.engines.base_engine import BaseEngine, QuoteResult, TradeResult
from backend.engines.clob_engine import CLOBEngine
from backend.models.enums import EngineType, OrderSide, OrderType, SymbolStatus


class EngineRouter:
    """
    Routes trading operations to the correct engine based on symbol configuration.

    This is the central dispatcher that:
    1. Looks up the symbol's engine type
    2. Instantiates the appropriate engine
    3. Delegates the operation to that engine
    
    Note: Same symbol can exist with different engine types (AMM and CLOB)
    for arbitrage opportunities. Use engine_type parameter to specify which engine.
    """

    def __init__(self, db_client):
        """
        Initialize the router with database client.

        Args:
            db_client: PostgreSQL async client
        """
        self.db = db_client
        # Cache key is now "symbol:engine_type" to support same symbol with different engines
        self._engine_cache: Dict[str, BaseEngine] = {}

    def _cache_key(self, symbol: str, engine_type: Optional[EngineType] = None) -> str:
        """Generate cache key for symbol + engine_type"""
        if engine_type is not None:
            return f"{symbol.upper()}:{engine_type.value}"
        return symbol.upper()

    async def _get_symbol_config(
        self, symbol: str, engine_type: Optional[EngineType] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get symbol configuration from database.
        
        Args:
            symbol: Symbol name
            engine_type: Specific engine type (AMM or CLOB). If None, returns first match.
        """
        if engine_type is not None:
            return await self.db.read_one(
                """
                SELECT * FROM symbol_configs
                WHERE symbol = $1 AND engine_type = $2 AND is_active = TRUE
                """,
                symbol.upper(),
                engine_type.value,
            )
        else:
            # If no engine_type specified, return first active match
            return await self.db.read_one(
                """
                SELECT * FROM symbol_configs
                WHERE symbol = $1 AND is_active = TRUE
                ORDER BY engine_type  -- AMM (0) first, then CLOB (1)
                LIMIT 1
                """,
                symbol.upper(),
            )

    async def _get_symbol_configs(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get all symbol configurations for a symbol (both AMM and CLOB if exist).
        
        Args:
            symbol: Symbol name
            
        Returns:
            List of symbol configs for all engine types
        """
        return await self.db.read(
            """
            SELECT * FROM symbol_configs
            WHERE symbol = $1 AND is_active = TRUE
            ORDER BY engine_type
            """,
            symbol.upper(),
        )

    async def _get_engine(
        self, symbol: str, engine_type: Optional[EngineType] = None
    ) -> Optional[BaseEngine]:
        """
        Get or create the appropriate engine for a symbol.

        Uses caching to avoid recreating engines for each request.
        
        Args:
            symbol: Symbol name
            engine_type: Specific engine type. If None, uses the symbol's configured engine.
        """
        symbol = symbol.upper()

        # Get symbol config first to determine engine_type if not specified
        config = await self._get_symbol_config(symbol, engine_type)
        if not config:
            return None

        actual_engine_type = EngineType(config["engine_type"])
        cache_key = self._cache_key(symbol, actual_engine_type)

        # Check cache
        if cache_key in self._engine_cache:
            return self._engine_cache[cache_key]

        # Create appropriate engine based on type
        if actual_engine_type == EngineType.AMM:
            engine = AMMEngine(self.db, config)
        elif actual_engine_type == EngineType.CLOB:
            engine = CLOBEngine(self.db, config)
        else:
            return None

        # Cache the engine
        self._engine_cache[cache_key] = engine
        return engine

    def invalidate_cache(self, symbol: Optional[str] = None, engine_type: Optional[EngineType] = None):
        """
        Invalidate engine cache.

        Args:
            symbol: Specific symbol to invalidate, or None to clear all
            engine_type: Specific engine type to invalidate
        """
        if symbol:
            if engine_type:
                cache_key = self._cache_key(symbol, engine_type)
                self._engine_cache.pop(cache_key, None)
            else:
                # Remove all engine types for this symbol
                keys_to_remove = [k for k in self._engine_cache if k.startswith(symbol.upper())]
                for key in keys_to_remove:
                    self._engine_cache.pop(key, None)
        else:
            self._engine_cache.clear()

    async def execute_trade(
        self,
        user_id: str,
        symbol: str,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        order_type: Optional[OrderType] = None,
        engine_type: Optional[EngineType] = None,
        **kwargs,
    ) -> TradeResult:
        """
        Execute a trade on the appropriate engine.

        This is the unified trade endpoint that routes to the correct engine.
        
        Args:
            user_id: User ID
            symbol: Symbol name
            side: BUY or SELL
            quantity: Amount to trade (base asset)
            quote_amount: Amount in quote asset (for AMM)
            price: Limit price (for CLOB)
            order_type: LIMIT or MARKET (for CLOB)
            engine_type: Specific engine (AMM or CLOB). Required if symbol exists on both.
        """
        engine = await self._get_engine(symbol, engine_type)

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
        engine_type: Optional[EngineType] = None,
        **kwargs,
    ) -> QuoteResult:
        """
        Get a quote for a potential trade.
        
        Args:
            symbol: Symbol name
            side: BUY or SELL
            quantity: Amount to trade
            quote_amount: Amount in quote asset
            engine_type: Specific engine (AMM or CLOB)
        """
        engine = await self._get_engine(symbol, engine_type)

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

    async def get_market_data(
        self, symbol: str, engine_type: Optional[EngineType] = None
    ) -> Dict[str, Any]:
        """
        Get market data for a symbol.
        
        Args:
            symbol: Symbol name
            engine_type: Specific engine (AMM or CLOB)
        """
        engine = await self._get_engine(symbol, engine_type)

        if not engine:
            return {"error": f"Symbol '{symbol}' not found or not active"}

        return await engine.get_market_data()

    async def get_all_symbols(self) -> list[Dict[str, Any]]:
        """
        Get all active symbols with their configurations.
        
        Note: Same symbol may appear multiple times with different engine_types.
        """
        return await self.db.read(
            """
            SELECT * FROM symbol_configs
            WHERE is_active = TRUE
            ORDER BY symbol, engine_type
            """
        )

    async def get_symbol_info(
        self, symbol: str, engine_type: Optional[EngineType] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a symbol.
        
        Args:
            symbol: Symbol name
            engine_type: Specific engine type
        """
        config = await self._get_symbol_config(symbol, engine_type)
        if not config:
            return None

        actual_engine_type = EngineType(config["engine_type"])
        market_data = await self.get_market_data(symbol, actual_engine_type)

        return {
            **config,
            "market_data": market_data,
        }

    async def get_symbol_engines(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get all available engines for a symbol (for arbitrage display).
        
        Args:
            symbol: Symbol name
            
        Returns:
            List of configs with market data for each engine type
        """
        configs = await self._get_symbol_configs(symbol)
        
        result = []
        for config in configs:
            engine_type = EngineType(config["engine_type"])
            market_data = await self.get_market_data(symbol, engine_type)
            result.append({
                **config,
                "market_data": market_data,
            })
        
        return result
