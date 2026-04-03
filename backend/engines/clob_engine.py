"""
CLOB (Central Limit Order Book) Engine

Implements traditional order book matching with price-time priority.
"""

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from backend.core.id_generator import generate_order_id, generate_trade_id
from backend.engines.base_engine import BaseEngine, QuoteResult, TradeResult
from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType, TradeStatus

# Minimum notional value for an order (price * quantity must exceed this)
DEFAULT_MIN_NOTIONAL = Decimal("1")


class CLOBEngine(BaseEngine):
    """
    Central Limit Order Book engine.

    Features:
    - Price-time priority matching
    - Limit and market orders
    - Maker/taker fee distinction
    - Partial fills support
    - Self-trade prevention
    - Atomic settlement via database transactions
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CLOB

    def _get_fee_rates(self) -> tuple[Decimal, Decimal]:
        """Get maker and taker fee rates from engine params"""
        maker_fee = Decimal(str(self.engine_params.get("maker_fee", "0.001")))
        taker_fee = Decimal(str(self.engine_params.get("taker_fee", "0.002")))
        return maker_fee, taker_fee

    def _get_min_notional(self) -> Decimal:
        """Get minimum notional value from engine params"""
        return Decimal(str(self.engine_params.get("min_notional", str(DEFAULT_MIN_NOTIONAL))))

    async def _get_best_orders(
        self,
        side: OrderSide,
        limit: int = 50,
        for_update: bool = False,
        conn=None,
    ) -> List[Dict[str, Any]]:
        """
        Get best orders from the order book.

        For BUY side: Get best SELL orders (lowest price first)
        For SELL side: Get best BUY orders (highest price first)

        Args:
            side: The incoming order side (we fetch the opposite side)
            limit: Max number of orders to fetch
            for_update: If True, lock rows with FOR UPDATE SKIP LOCKED
            conn: Optional database connection (for use within a transaction)
        """
        opposite_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY

        if opposite_side == OrderSide.SELL:
            order_clause = "price ASC, created_at ASC"
        else:
            order_clause = "price DESC, created_at ASC"

        lock_clause = "FOR UPDATE SKIP LOCKED" if for_update else ""

        query = f"""
            SELECT * FROM orderbook_orders
            WHERE symbol_id = $1
            AND side = $2
            AND status IN ({OrderStatus.OPEN.value}, {OrderStatus.PARTIAL.value})
            AND price IS NOT NULL
            ORDER BY {order_clause}
            LIMIT $3
            {lock_clause}
        """

        if conn:
            rows = await conn.fetch(query, self.symbol_config["symbol_id"], opposite_side.value, limit)
            return [dict(r) for r in rows]

        return await self.db.read(
            query,
            self.symbol_config["symbol_id"],
            opposite_side.value,
            limit,
        )

    async def _get_order_book(self, levels: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """Get aggregated order book with bid/ask levels"""
        bids = await self.db.read(
            f"""
            SELECT price, SUM(remaining_quantity) as quantity, COUNT(*) as order_count
            FROM orderbook_orders
            WHERE symbol_id = $1
            AND side = {OrderSide.BUY.value}
            AND status IN ({OrderStatus.OPEN.value}, {OrderStatus.PARTIAL.value})
            AND price IS NOT NULL
            GROUP BY price
            ORDER BY price DESC
            LIMIT $2
            """,
            self.symbol_config["symbol_id"],
            levels,
        )

        asks = await self.db.read(
            f"""
            SELECT price, SUM(remaining_quantity) as quantity, COUNT(*) as order_count
            FROM orderbook_orders
            WHERE symbol_id = $1
            AND side = {OrderSide.SELL.value}
            AND status IN ({OrderStatus.OPEN.value}, {OrderStatus.PARTIAL.value})
            AND price IS NOT NULL
            GROUP BY price
            ORDER BY price ASC
            LIMIT $2
            """,
            self.symbol_config["symbol_id"],
            levels,
        )

        return {"bids": bids, "asks": asks}

    async def _create_order(
        self,
        user_id: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal],
    ) -> str:
        """Create a new order in the order book"""
        order_id = generate_order_id()

        result = await self.db.execute_returning(
            """
            INSERT INTO orderbook_orders (
                order_id, symbol_id, user_id, side, order_type,
                price, quantity, remaining_quantity, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $7, $8)
            RETURNING order_id
            """,
            order_id,
            self.symbol_config["symbol_id"],
            user_id,
            side.value,
            order_type.value,
            price,
            quantity,
            OrderStatus.OPEN.value,
        )
        return result["order_id"]

    async def _update_order(
        self,
        order_id: str,
        filled_amount: Decimal,
        new_status: OrderStatus,
        conn=None,
    ) -> bool:
        """Update order after a fill"""
        if new_status == OrderStatus.FILLED:
            query = """
                UPDATE orderbook_orders
                SET filled_quantity = filled_quantity + $2,
                    remaining_quantity = remaining_quantity - $2,
                    status = $3,
                    filled_at = NOW(),
                    updated_at = NOW()
                WHERE order_id = $1
            """
        else:
            query = """
                UPDATE orderbook_orders
                SET filled_quantity = filled_quantity + $2,
                    remaining_quantity = remaining_quantity - $2,
                    status = $3,
                    updated_at = NOW()
                WHERE order_id = $1
            """

        if conn:
            result = await conn.execute(query, order_id, filled_amount, new_status.value)
            return "UPDATE 1" in result

        result = await self.db.execute(query, order_id, filled_amount, new_status.value)
        return "UPDATE 1" in result

    async def _lock_balance(self, user_id: str, asset: str, amount: Decimal) -> bool:
        """Lock balance for a pending order"""
        result = await self.db.execute(
            """
            UPDATE user_balances
            SET available = available - $3,
                locked = locked + $3,
                updated_at = NOW()
            WHERE user_id = $1 AND currency = $2
            AND available >= $3
            """,
            user_id,
            asset,
            amount,
        )
        return "UPDATE 1" in result

    async def _unlock_balance(self, user_id: str, asset: str, amount: Decimal) -> bool:
        """Unlock balance when order is cancelled or filled"""
        if amount <= 0:
            return True
        result = await self.db.execute(
            """
            UPDATE user_balances
            SET available = available + $3,
                locked = locked - $3,
                updated_at = NOW()
            WHERE user_id = $1 AND currency = $2
            AND locked >= $3
            """,
            user_id,
            asset,
            amount,
        )
        return "UPDATE 1" in result

    async def _settle_trade_atomic(
        self,
        conn,
        buyer_id: str,
        seller_id: str,
        price: Decimal,
        quantity: Decimal,
        buyer_fee: Decimal,
        seller_fee: Decimal,
    ) -> bool:
        """
        Settle a trade atomically within an existing transaction connection.

        Buyer: locked quote deducted, available base added (minus fee)
        Seller: locked base deducted, available quote added (minus fee)
        """
        quote_amount = price * quantity

        # All 4 balance updates use the same connection (already in a transaction)
        # 1. Buyer: deduct locked quote
        r1 = await conn.execute(
            """
            UPDATE user_balances
            SET locked = locked - $3,
                balance = balance - $3,
                updated_at = NOW()
            WHERE user_id = $1 AND currency = $2 AND locked >= $3
            """,
            buyer_id,
            self.quote_asset,
            quote_amount,
        )

        # 2. Buyer: add available base (minus buyer fee)
        base_received = quantity - buyer_fee
        r2 = await conn.execute(
            """
            UPDATE user_balances
            SET available = available + $3,
                balance = balance + $3,
                updated_at = NOW()
            WHERE user_id = $1 AND currency = $2
            """,
            buyer_id,
            self.base_asset,
            base_received,
        )

        # 3. Seller: deduct locked base
        r3 = await conn.execute(
            """
            UPDATE user_balances
            SET locked = locked - $3,
                balance = balance - $3,
                updated_at = NOW()
            WHERE user_id = $1 AND currency = $2 AND locked >= $3
            """,
            seller_id,
            self.base_asset,
            quantity,
        )

        # 4. Seller: add available quote (minus seller fee)
        quote_received = quote_amount - seller_fee
        r4 = await conn.execute(
            """
            UPDATE user_balances
            SET available = available + $3,
                balance = balance + $3,
                updated_at = NOW()
            WHERE user_id = $1 AND currency = $2
            """,
            seller_id,
            self.quote_asset,
            quote_received,
        )

        # 5. Record protocol fee
        total_fee = buyer_fee + seller_fee
        if total_fee > 0:
            await conn.execute(
                """
                INSERT INTO protocol_fees (symbol_id, fee_amount, fee_asset, source)
                VALUES ($1, $2, $3, 'clob_trade')
                """,
                self.symbol_config["symbol_id"],
                total_fee,
                self.quote_asset,
            )

        return all("UPDATE 1" in r for r in [r1, r2, r3, r4])

    async def execute_trade(
        self,
        user_id: str,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs,
    ) -> TradeResult:
        """
        Execute a CLOB order with atomic settlement.

        For limit orders: Add to book if no match, or fill if matching orders exist
        For market orders: Fill immediately against existing orders
        """
        if quantity is None:
            return TradeResult(
                success=False,
                error_message="quantity is required for CLOB orders",
            )

        if order_type == OrderType.LIMIT and price is None:
            return TradeResult(
                success=False,
                error_message="price is required for limit orders",
            )

        # Minimum notional validation for limit orders
        min_notional = self._get_min_notional()
        if order_type == OrderType.LIMIT and price is not None:
            notional = price * quantity
            if notional < min_notional:
                return TradeResult(
                    success=False,
                    error_message=f"Order notional ({notional}) below minimum ({min_notional})",
                )

        maker_fee_rate, taker_fee_rate = self._get_fee_rates()

        # Calculate required balance and lock it
        if side == OrderSide.BUY:
            if order_type == OrderType.LIMIT:
                required_amount = price * quantity
            else:
                # For market buy: estimate from best ASK (sell orders)
                best_asks = await self._get_best_orders(OrderSide.BUY, 50)
                if not best_asks:
                    return TradeResult(
                        success=False,
                        error_message="No sell orders available for market buy",
                    )
                # Calculate exact required amount from available depth
                remaining_qty = quantity
                estimated_cost = Decimal("0")
                for ask in best_asks:
                    ask_price = Decimal(str(ask["price"]))
                    ask_qty = Decimal(str(ask["remaining_quantity"]))
                    fill_qty = min(remaining_qty, ask_qty)
                    estimated_cost += ask_price * fill_qty
                    remaining_qty -= fill_qty
                    if remaining_qty <= 0:
                        break
                # Add 5% safety margin for the depth-based estimate
                required_amount = estimated_cost * Decimal("1.05")

            lock_asset = self.quote_asset
        else:
            required_amount = quantity
            lock_asset = self.base_asset

        # Check and lock balance
        if not await self.validate_balance(user_id, lock_asset, required_amount):
            return TradeResult(
                success=False,
                error_message=f"Insufficient {lock_asset} balance",
            )

        if not await self._lock_balance(user_id, lock_asset, required_amount):
            return TradeResult(
                success=False,
                error_message=f"Failed to lock {lock_asset} balance",
            )

        # Match and settle within a transaction
        fills: List[Dict[str, Any]] = []
        remaining_quantity = quantity
        total_filled_quantity = Decimal("0")
        total_quote_amount = Decimal("0")
        total_fee = Decimal("0")
        first_taker_trade_id: Optional[str] = None

        try:
            async with self.db.transaction() as conn:
                # Get matching orders with row-level locks to prevent race conditions
                matching_orders = await self._get_best_orders(
                    side, limit=50, for_update=True, conn=conn
                )

                for order in matching_orders:
                    if remaining_quantity <= 0:
                        break

                    # Self-trade prevention: skip own orders
                    if order["user_id"] == user_id:
                        continue

                    order_price = Decimal(str(order["price"]))
                    order_remaining = Decimal(str(order["remaining_quantity"]))

                    # Check if price matches (limit orders only)
                    if order_type == OrderType.LIMIT:
                        if side == OrderSide.BUY and order_price > price:
                            break
                        if side == OrderSide.SELL and order_price < price:
                            break

                    # Calculate fill
                    fill_quantity = min(remaining_quantity, order_remaining)
                    fill_quote = order_price * fill_quantity

                    taker_fee = fill_quote * taker_fee_rate
                    maker_fee = fill_quote * maker_fee_rate

                    if side == OrderSide.BUY:
                        buyer_id = user_id
                        seller_id = order["user_id"]
                        buyer_fee = taker_fee
                        seller_fee = maker_fee
                    else:
                        buyer_id = order["user_id"]
                        seller_id = user_id
                        buyer_fee = maker_fee
                        seller_fee = taker_fee

                    # Atomic settlement within the transaction
                    if not await self._settle_trade_atomic(
                        conn, buyer_id, seller_id,
                        order_price, fill_quantity,
                        buyer_fee, seller_fee,
                    ):
                        break

                    # Update matched order status
                    new_status = (
                        OrderStatus.FILLED if fill_quantity >= order_remaining else OrderStatus.PARTIAL
                    )
                    await self._update_order(order["order_id"], fill_quantity, new_status, conn=conn)

                    # Record taker trade
                    taker_trade_id = generate_trade_id()
                    await conn.execute(
                        """
                        INSERT INTO trades (
                            trade_id, symbol_id, user_id, side, engine_type,
                            price, quantity, quote_amount,
                            fee_amount, fee_asset, status, engine_data, counterparty
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
                        taker_trade_id,
                        self.symbol_config["symbol_id"],
                        user_id,
                        side.value,
                        EngineType.CLOB.value,
                        order_price,
                        fill_quantity,
                        fill_quote,
                        taker_fee,
                        self.quote_asset,
                        TradeStatus.COMPLETED.value,
                        json.dumps({"is_taker": True, "matched_order_id": order["order_id"]}),
                        order["user_id"],
                    )

                    # Record maker trade
                    maker_trade_id = generate_trade_id()
                    maker_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY
                    await conn.execute(
                        """
                        INSERT INTO trades (
                            trade_id, symbol_id, user_id, side, engine_type,
                            price, quantity, quote_amount,
                            fee_amount, fee_asset, status, engine_data, counterparty
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
                        maker_trade_id,
                        self.symbol_config["symbol_id"],
                        order["user_id"],
                        maker_side.value,
                        EngineType.CLOB.value,
                        order_price,
                        fill_quantity,
                        fill_quote,
                        maker_fee,
                        self.quote_asset,
                        TradeStatus.COMPLETED.value,
                        json.dumps({"is_taker": False, "matched_order_id": order["order_id"]}),
                        user_id,
                    )

                    if first_taker_trade_id is None:
                        first_taker_trade_id = taker_trade_id

                    fills.append(
                        {
                            "trade_id": taker_trade_id,
                            "price": float(order_price),
                            "quantity": float(fill_quantity),
                            "quote_amount": float(fill_quote),
                            "fee": float(taker_fee),
                            "matched_order_id": order["order_id"],
                            # Extra fields for private WS events
                            "maker_user_id": order["user_id"],
                            "maker_trade_id": maker_trade_id,
                            "maker_fee": float(maker_fee),
                            "maker_side": maker_side.value,
                            "maker_order_status": new_status.value,
                            "maker_remaining": float(order_remaining - fill_quantity),
                        }
                    )

                    remaining_quantity -= fill_quantity
                    total_filled_quantity += fill_quantity
                    total_quote_amount += fill_quote
                    total_fee += taker_fee

        except Exception as e:
            # Transaction auto-rolled back. Unlock the full locked amount.
            await self._unlock_balance(user_id, lock_asset, required_amount)
            return TradeResult(
                success=False,
                error_message=f"Trade execution failed: {str(e)}",
            )

        # Handle unfilled quantity
        order_id = None
        if remaining_quantity > 0 and order_type == OrderType.LIMIT:
            # Rest remaining quantity on the book
            order_id = await self._create_order(
                user_id, side, order_type, remaining_quantity, price,
            )
        elif remaining_quantity > 0 and side == OrderSide.BUY:
            # Market buy: unlock unused locked quote
            actual_used_quote = sum(Decimal(str(f["quote_amount"])) for f in fills)
            unused_quote = required_amount - actual_used_quote
            await self._unlock_balance(user_id, self.quote_asset, unused_quote)
        elif remaining_quantity > 0 and side == OrderSide.SELL:
            # Market sell: unlock remaining base
            await self._unlock_balance(user_id, self.base_asset, remaining_quantity)

        # Market order with no fills
        if total_filled_quantity == 0 and order_type == OrderType.MARKET:
            await self._unlock_balance(user_id, lock_asset, required_amount)
            return TradeResult(
                success=False,
                error_message="No matching orders found",
            )

        avg_price = total_quote_amount / total_filled_quantity if total_filled_quantity > 0 else Decimal("0")

        # Fire-and-forget WebSocket broadcast (if manager available)
        asyncio.create_task(self._broadcast_trade_event(user_id, side, fills))

        return TradeResult(
            success=True,
            trade_id=first_taker_trade_id,
            symbol=self.symbol,
            side=side,
            engine_type=EngineType.CLOB,
            price=avg_price,
            quantity=total_filled_quantity,
            quote_amount=total_quote_amount,
            fee_amount=total_fee,
            fee_asset=self.quote_asset,
            status=TradeStatus.COMPLETED if remaining_quantity == 0 else TradeStatus.PENDING,
            order_id=order_id,
            fills=fills,
            engine_data={
                "order_type": order_type.value,
                "filled_quantity": float(total_filled_quantity),
                "remaining_quantity": float(remaining_quantity),
                "fills_count": len(fills),
            },
        )

    async def _broadcast_trade_event(
        self, taker_user_id: str, side: OrderSide, fills: List[Dict[str, Any]]
    ):
        """Broadcast trade events via WebSocket (no-op if manager not available)"""
        try:
            from backend.core.websocket_manager import get_ws_manager
            manager = get_ws_manager()
            if not manager or not fills:
                return

            symbol = self.symbol
            now_iso = datetime.now(timezone.utc).isoformat()

            for fill in fills:
                # --- Public channel: trades:{symbol} (Issue #20: enriched payload) ---
                await manager.broadcast(f"trades:{symbol}", {
                    "type": "trade",
                    "symbol": symbol,
                    "price": fill["price"],
                    "quantity": fill["quantity"],
                    "side": side.value,
                    "trade_id": fill["trade_id"],
                    "created_at": now_iso,
                })

                # --- Private channel: taker order_update ---
                await manager.send_to_user(taker_user_id, {
                    "type": "order_update",
                    "order_id": fill["matched_order_id"],
                    "symbol": symbol,
                    "side": side.value,
                    "status": OrderStatus.FILLED.value,
                    "filled_quantity": fill["quantity"],
                    "remaining_quantity": 0,
                    "price": fill["price"],
                    "fill_price": fill["price"],
                    "fee_amount": fill["fee"],
                    "fee_asset": self.quote_asset,
                    "trade_id": fill["trade_id"],
                    "is_taker": True,
                })

                # --- Private channel: maker order_update ---
                maker_user_id = fill["maker_user_id"]
                await manager.send_to_user(maker_user_id, {
                    "type": "order_update",
                    "order_id": fill["matched_order_id"],
                    "symbol": symbol,
                    "side": fill["maker_side"],
                    "status": fill["maker_order_status"],
                    "filled_quantity": fill["quantity"],
                    "remaining_quantity": fill["maker_remaining"],
                    "price": fill["price"],
                    "fill_price": fill["price"],
                    "fee_amount": fill["maker_fee"],
                    "fee_asset": self.quote_asset,
                    "trade_id": fill["maker_trade_id"],
                    "is_taker": False,
                })

            # --- Public channel: orderbook:{symbol} ---
            order_book = await self._get_order_book(20)
            await manager.broadcast(f"orderbook:{symbol}", {
                "type": "orderbook",
                "symbol": symbol,
                "bids": order_book["bids"],
                "asks": order_book["asks"],
            })
        except Exception:
            pass  # WebSocket broadcast is best-effort

    async def get_quote(
        self,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        **kwargs,
    ) -> QuoteResult:
        """Get a quote by simulating order matching"""
        if quantity is None:
            return QuoteResult(
                success=False,
                error_message="quantity is required for CLOB quote",
            )

        matching_orders = await self._get_best_orders(side)

        if not matching_orders:
            return QuoteResult(
                success=False,
                error_message="No matching orders available",
            )

        _, taker_fee_rate = self._get_fee_rates()

        remaining = quantity
        total_quote = Decimal("0")
        simulated_fills = []

        for order in matching_orders:
            if remaining <= 0:
                break

            order_price = Decimal(str(order["price"]))
            order_remaining = Decimal(str(order["remaining_quantity"]))

            fill_qty = min(remaining, order_remaining)
            fill_quote = order_price * fill_qty

            simulated_fills.append(
                {
                    "price": float(order_price),
                    "quantity": float(fill_qty),
                }
            )

            remaining -= fill_qty
            total_quote += fill_quote

        filled_quantity = quantity - remaining
        fee_amount = total_quote * taker_fee_rate
        avg_price = total_quote / filled_quantity if filled_quantity > 0 else Decimal("0")

        if side == OrderSide.BUY:
            input_asset = self.quote_asset
            input_amount = total_quote
            output_asset = self.base_asset
            output_amount = filled_quantity
        else:
            input_asset = self.base_asset
            input_amount = filled_quantity
            output_asset = self.quote_asset
            output_amount = total_quote - fee_amount

        return QuoteResult(
            success=True,
            input_amount=input_amount,
            input_asset=input_asset,
            output_amount=output_amount,
            output_asset=output_asset,
            effective_price=avg_price,
            fee_amount=fee_amount,
            fee_asset=self.quote_asset,
            error_message=f"Only {filled_quantity} of {quantity} can be filled" if remaining > 0 else None,
        )

    async def get_market_data(self) -> Dict[str, Any]:
        """Get current market data for order book"""
        order_book = await self._get_order_book(5)

        best_bid = Decimal(str(order_book["bids"][0]["price"])) if order_book["bids"] else None
        best_ask = Decimal(str(order_book["asks"][0]["price"])) if order_book["asks"] else None

        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_pct = (spread / mid_price) * 100 if mid_price > 0 else None
        else:
            mid_price = best_bid or best_ask or Decimal("0")
            spread = None
            spread_pct = None

        last_trade = await self.db.read_one(
            """
            SELECT price, quantity, created_at FROM trades
            WHERE symbol_id = $1 AND engine_type = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            self.symbol_config["symbol_id"],
            EngineType.CLOB.value,
        )

        return {
            "symbol": self.symbol,
            "engine_type": EngineType.CLOB.value,
            "current_price": float(last_trade["price"]) if last_trade else float(mid_price),
            "best_bid": float(best_bid) if best_bid else None,
            "best_ask": float(best_ask) if best_ask else None,
            "spread": float(spread) if spread else None,
            "spread_pct": float(spread_pct) if spread_pct else None,
            "bids": order_book["bids"],
            "asks": order_book["asks"],
        }

    async def cancel_order(self, user_id: str, order_id: str) -> Dict[str, Any]:
        """Cancel an open order with race-condition safety"""
        async with self.db.transaction() as conn:
            # Lock the order row to prevent concurrent cancel + fill
            row = await conn.fetchrow(
                f"""
                SELECT * FROM orderbook_orders
                WHERE order_id = $1 AND user_id = $2
                AND status IN ({OrderStatus.OPEN.value}, {OrderStatus.PARTIAL.value})
                FOR UPDATE
                """,
                order_id,
                user_id,
            )

            if not row:
                return {"success": False, "error": "Order not found or already filled/cancelled"}

            order = dict(row)
            remaining = Decimal(str(order["remaining_quantity"]))

            # Use int comparison (DB returns int for side)
            if order["side"] == OrderSide.BUY.value:
                unlock_asset = self.quote_asset
                unlock_amount = Decimal(str(order["price"])) * remaining
            else:
                unlock_asset = self.base_asset
                unlock_amount = remaining

            # Unlock balance
            await conn.execute(
                """
                UPDATE user_balances
                SET available = available + $3,
                    locked = locked - $3,
                    updated_at = NOW()
                WHERE user_id = $1 AND currency = $2
                AND locked >= $3
                """,
                user_id,
                unlock_asset,
                unlock_amount,
            )

            # Update order status
            await conn.execute(
                """
                UPDATE orderbook_orders
                SET status = $2,
                    cancelled_at = NOW(),
                    updated_at = NOW()
                WHERE order_id = $1
                """,
                order_id,
                OrderStatus.CANCELLED.value,
            )

        # Fire-and-forget: notify user via private WS channel
        asyncio.create_task(self._broadcast_cancel_event(user_id, order_id, order))

        return {
            "success": True,
            "order_id": order_id,
            "unlocked_amount": float(unlock_amount),
            "unlocked_asset": unlock_asset,
        }

    async def _broadcast_cancel_event(
        self, user_id: str, order_id: str, order: Dict[str, Any]
    ):
        """Broadcast cancel event to user's private channel"""
        try:
            from backend.core.websocket_manager import get_ws_manager
            manager = get_ws_manager()
            if not manager:
                return

            await manager.send_to_user(user_id, {
                "type": "order_update",
                "order_id": order_id,
                "symbol": self.symbol,
                "side": order["side"],
                "status": OrderStatus.CANCELLED.value,
                "filled_quantity": float(order["filled_quantity"]),
                "remaining_quantity": 0,
                "price": float(order["price"]) if order["price"] else None,
                "fee_amount": 0,
                "fee_asset": self.quote_asset,
            })

            # Also update public orderbook
            order_book = await self._get_order_book(20)
            await manager.broadcast(f"orderbook:{self.symbol}", {
                "type": "orderbook",
                "symbol": self.symbol,
                "bids": order_book["bids"],
                "asks": order_book["asks"],
            })
        except Exception:
            pass
