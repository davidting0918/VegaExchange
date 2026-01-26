"""
CLOB (Central Limit Order Book) Engine

Implements traditional order book matching with price-time priority.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.engines.base_engine import BaseEngine, QuoteResult, TradeResult
from backend.models.enums import EngineType, OrderSide, OrderStatus, OrderType, TradeStatus


class CLOBEngine(BaseEngine):
    """
    Central Limit Order Book engine.

    Features:
    - Price-time priority matching
    - Limit and market orders
    - Maker/taker fee distinction
    - Partial fills support
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CLOB

    def _get_fee_rates(self) -> tuple[Decimal, Decimal]:
        """Get maker and taker fee rates from engine params"""
        maker_fee = Decimal(str(self.engine_params.get("maker_fee", "0.001")))  # 0.1% default
        taker_fee = Decimal(str(self.engine_params.get("taker_fee", "0.002")))  # 0.2% default
        return maker_fee, taker_fee

    async def _get_best_orders(
        self,
        side: OrderSide,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get best orders from the order book.

        For BUY side: Get best SELL orders (lowest price first)
        For SELL side: Get best BUY orders (highest price first)
        """
        opposite_side = OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY

        if opposite_side == OrderSide.SELL:
            # Get sell orders, lowest price first
            order_clause = "price ASC, created_at ASC"
        else:
            # Get buy orders, highest price first
            order_clause = "price DESC, created_at ASC"

        orders = await self.db.read(
            f"""
            SELECT * FROM orderbook_orders
            WHERE symbol_config_id = $1
            AND side = $2
            AND status IN ({OrderStatus.OPEN}, {OrderStatus.PARTIAL})
            AND price IS NOT NULL
            ORDER BY {order_clause}
            LIMIT $3
            """,
            self.symbol_config["id"],
            opposite_side.value,
            limit,
        )

        return orders

    async def _get_order_book(self, levels: int = 20) -> Dict[str, List[Dict[str, Any]]]:
        """Get aggregated order book with bid/ask levels"""
        bids = await self.db.read(
            f"""
            SELECT price, SUM(remaining_quantity) as quantity, COUNT(*) as order_count
            FROM orderbook_orders
            WHERE symbol_config_id = $1
            AND side = {OrderSide.BUY}
            AND status IN ({OrderStatus.OPEN}, {OrderStatus.PARTIAL})
            AND price IS NOT NULL
            GROUP BY price
            ORDER BY price DESC
            LIMIT $2
            """,
            self.symbol_config["id"],
            levels,
        )

        asks = await self.db.read(
            f"""
            SELECT price, SUM(remaining_quantity) as quantity, COUNT(*) as order_count
            FROM orderbook_orders
            WHERE symbol_config_id = $1
            AND side = {OrderSide.SELL}
            AND status IN ({OrderStatus.OPEN}, {OrderStatus.PARTIAL})
            AND price IS NOT NULL
            GROUP BY price
            ORDER BY price ASC
            LIMIT $2
            """,
            self.symbol_config["id"],
            levels,
        )

        return {"bids": bids, "asks": asks}

    async def _create_order(
        self,
        user_id: UUID,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal],
    ) -> UUID:
        """Create a new order in the order book"""
        result = await self.db.execute_returning(
            """
            INSERT INTO orderbook_orders (
                symbol_config_id, user_id, side, order_type,
                price, quantity, remaining_quantity, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $6, $7)
            RETURNING id
            """,
            self.symbol_config["id"],
            user_id,
            side.value,
            order_type.value,
            price,
            quantity,
            OrderStatus.OPEN.value,
        )
        return result["id"]

    async def _update_order(
        self,
        order_id: UUID,
        filled_amount: Decimal,
        new_status: OrderStatus,
    ) -> bool:
        """Update order after a fill"""
        if new_status == OrderStatus.FILLED:
            result = await self.db.execute(
                """
                UPDATE orderbook_orders
                SET filled_quantity = filled_quantity + $2,
                    remaining_quantity = remaining_quantity - $2,
                    status = $3,
                    filled_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
                """,
                order_id,
                filled_amount,
                new_status.value,
            )
        else:
            result = await self.db.execute(
                """
                UPDATE orderbook_orders
                SET filled_quantity = filled_quantity + $2,
                    remaining_quantity = remaining_quantity - $2,
                    status = $3,
                    updated_at = NOW()
                WHERE id = $1
                """,
                order_id,
                filled_amount,
                new_status.value,
            )
        return "UPDATE 1" in result

    async def _lock_balance(self, user_id: UUID, asset: str, amount: Decimal) -> bool:
        """Lock balance for a pending order"""
        result = await self.db.execute(
            """
            UPDATE user_balances
            SET available = available - $3,
                locked = locked + $3,
                updated_at = NOW()
            WHERE user_id = $1 AND asset = $2
            AND available >= $3
            """,
            user_id,
            asset,
            amount,
        )
        return "UPDATE 1" in result

    async def _unlock_balance(self, user_id: UUID, asset: str, amount: Decimal) -> bool:
        """Unlock balance when order is cancelled or filled"""
        result = await self.db.execute(
            """
            UPDATE user_balances
            SET available = available + $3,
                locked = locked - $3,
                updated_at = NOW()
            WHERE user_id = $1 AND asset = $2
            AND locked >= $3
            """,
            user_id,
            asset,
            amount,
        )
        return "UPDATE 1" in result

    async def _settle_trade(
        self,
        buyer_id: UUID,
        seller_id: UUID,
        price: Decimal,
        quantity: Decimal,
        buyer_fee: Decimal,
        seller_fee: Decimal,
    ) -> bool:
        """
        Settle a trade between buyer and seller.

        Buyer: pays quote_amount (locked), receives base_asset - fee
        Seller: pays base_asset (locked), receives quote_amount - fee
        """
        quote_amount = price * quantity

        # Buyer: deduct locked quote, add base
        buyer_quote_ok = await self.db.execute(
            """
            UPDATE user_balances
            SET locked = locked - $3,
                updated_at = NOW()
            WHERE user_id = $1 AND asset = $2
            AND locked >= $3
            """,
            buyer_id,
            self.quote_asset,
            quote_amount,
        )

        buyer_base_ok = await self.update_balance(
            buyer_id,
            self.base_asset,
            quantity - buyer_fee,
        )

        # Seller: deduct locked base, add quote
        seller_base_ok = await self.db.execute(
            """
            UPDATE user_balances
            SET locked = locked - $3,
                updated_at = NOW()
            WHERE user_id = $1 AND asset = $2
            AND locked >= $3
            """,
            seller_id,
            self.base_asset,
            quantity,
        )

        seller_quote_ok = await self.update_balance(
            seller_id,
            self.quote_asset,
            quote_amount - seller_fee,
        )

        return all(
            [
                "UPDATE 1" in buyer_quote_ok,
                buyer_base_ok,
                "UPDATE 1" in seller_base_ok,
                seller_quote_ok,
            ]
        )

    async def execute_trade(
        self,
        user_id: UUID,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        order_type: OrderType = OrderType.LIMIT,
        **kwargs,
    ) -> TradeResult:
        """
        Execute a CLOB order.

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

        maker_fee_rate, taker_fee_rate = self._get_fee_rates()

        # Calculate required balance and lock it
        if side == OrderSide.BUY:
            # Buyer needs to lock quote asset
            if order_type == OrderType.LIMIT:
                required_amount = price * quantity
            else:
                # For market orders, we need to estimate
                # Get best ask to estimate cost
                asks = await self._get_best_orders(OrderSide.BUY, 1)
                if not asks:
                    return TradeResult(
                        success=False,
                        error_message="No sell orders available for market buy",
                    )
                # Use best ask price * 1.1 as safety margin
                estimated_price = Decimal(str(asks[0]["price"])) * Decimal("1.1")
                required_amount = estimated_price * quantity

            lock_asset = self.quote_asset
        else:
            # Seller needs to lock base asset
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

        # Get matching orders
        matching_orders = await self._get_best_orders(side)

        fills: List[Dict[str, Any]] = []
        remaining_quantity = quantity
        total_filled_quantity = Decimal("0")
        total_quote_amount = Decimal("0")
        total_fee = Decimal("0")

        # Try to match against existing orders
        for order in matching_orders:
            if remaining_quantity <= 0:
                break

            order_price = Decimal(str(order["price"]))
            order_remaining = Decimal(str(order["remaining_quantity"]))

            # Check if price matches
            if order_type == OrderType.LIMIT:
                if side == OrderSide.BUY and order_price > price:
                    break  # No more matches possible
                if side == OrderSide.SELL and order_price < price:
                    break

            # Calculate fill amount
            fill_quantity = min(remaining_quantity, order_remaining)
            fill_quote = order_price * fill_quantity

            # Determine maker/taker
            # The existing order is the maker, incoming order is taker
            taker_fee = fill_quote * taker_fee_rate
            maker_fee = fill_quote * maker_fee_rate

            # Settle the trade
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

            if not await self._settle_trade(
                buyer_id,
                seller_id,
                order_price,
                fill_quantity,
                buyer_fee,
                seller_fee,
            ):
                # Settlement failed, stop matching
                break

            # Update the matched order
            new_status = (
                OrderStatus.FILLED if fill_quantity >= order_remaining else OrderStatus.PARTIAL
            )
            await self._update_order(order["id"], fill_quantity, new_status)

            # Record trades for both parties
            # Taker trade (incoming order)
            taker_trade_id = await self.record_trade(
                user_id=user_id,
                side=side,
                price=order_price,
                quantity=fill_quantity,
                quote_amount=fill_quote,
                fee_amount=taker_fee,
                fee_asset=self.quote_asset,
                status=TradeStatus.COMPLETED,
                engine_data={"is_taker": True, "matched_order_id": str(order["id"])},
                counterparty_user_id=order["user_id"],
            )

            # Maker trade (existing order)
            await self.record_trade(
                user_id=order["user_id"],
                side=OrderSide.SELL if side == OrderSide.BUY else OrderSide.BUY,
                price=order_price,
                quantity=fill_quantity,
                quote_amount=fill_quote,
                fee_amount=maker_fee,
                fee_asset=self.quote_asset,
                status=TradeStatus.COMPLETED,
                engine_data={"is_taker": False, "matched_order_id": str(order["id"])},
                counterparty_user_id=user_id,
            )

            fills.append(
                {
                    "price": float(order_price),
                    "quantity": float(fill_quantity),
                    "quote_amount": float(fill_quote),
                    "fee": float(taker_fee),
                    "matched_order_id": str(order["id"]),
                }
            )

            remaining_quantity -= fill_quantity
            total_filled_quantity += fill_quantity
            total_quote_amount += fill_quote
            total_fee += taker_fee

        # Handle unfilled quantity for limit orders
        order_id = None
        if remaining_quantity > 0 and order_type == OrderType.LIMIT:
            # Create a new order for the remaining quantity
            order_id = await self._create_order(
                user_id,
                side,
                order_type,
                remaining_quantity,
                price,
            )
        elif remaining_quantity > 0:
            # Market order couldn't fill completely - unlock remaining
            if side == OrderSide.BUY:
                # Unlock unused quote
                asks = await self._get_best_orders(OrderSide.BUY, 1)
                if asks:
                    estimated_price = Decimal(str(asks[0]["price"])) * Decimal("1.1")
                    unused_quote = estimated_price * remaining_quantity
                    await self._unlock_balance(user_id, self.quote_asset, unused_quote)
            else:
                # Unlock remaining base
                await self._unlock_balance(user_id, self.base_asset, remaining_quantity)

        # Calculate average price
        avg_price = total_quote_amount / total_filled_quantity if total_filled_quantity > 0 else Decimal("0")

        if total_filled_quantity == 0 and order_type == OrderType.MARKET:
            # Market order with no fills
            await self._unlock_balance(user_id, lock_asset, required_amount)
            return TradeResult(
                success=False,
                error_message="No matching orders found",
            )

        return TradeResult(
            success=True,
            trade_id=fills[0]["matched_order_id"] if fills else None,
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

        # Calculate mid price and spread
        if best_bid and best_ask:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_pct = (spread / mid_price) * 100 if mid_price > 0 else None
        else:
            mid_price = best_bid or best_ask or Decimal("0")
            spread = None
            spread_pct = None

        # Get recent trade for current price
        last_trade = await self.db.read_one(
            """
            SELECT price, quantity, created_at FROM trades
            WHERE symbol_config_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            self.symbol_config["id"],
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

    async def cancel_order(self, user_id: UUID, order_id: UUID) -> Dict[str, Any]:
        """Cancel an open order"""
        # Get order details
        order = await self.db.read_one(
            f"""
            SELECT * FROM orderbook_orders
            WHERE id = $1 AND user_id = $2
            AND status IN ({OrderStatus.OPEN}, {OrderStatus.PARTIAL})
            """,
            order_id,
            user_id,
        )

        if not order:
            return {"success": False, "error": "Order not found or already filled/cancelled"}

        # Unlock remaining balance
        remaining = Decimal(str(order["remaining_quantity"]))
        if order["side"] == OrderSide.BUY:
            unlock_asset = self.quote_asset
            unlock_amount = Decimal(str(order["price"])) * remaining
        else:
            unlock_asset = self.base_asset
            unlock_amount = remaining

        await self._unlock_balance(user_id, unlock_asset, unlock_amount)

        # Update order status
        await self.db.execute(
            """
            UPDATE orderbook_orders
            SET status = $2,
                cancelled_at = NOW(),
                updated_at = NOW()
            WHERE id = $1
            """,
            order_id,
            OrderStatus.CANCELLED.value,
        )

        return {
            "success": True,
            "order_id": str(order_id),
            "unlocked_amount": float(unlock_amount),
            "unlocked_asset": unlock_asset,
        }

    async def get_user_orders(
        self,
        user_id: UUID,
        status: Optional[List[OrderStatus]] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get user's orders"""
        if status:
            status_values = [s.value for s in status]
            orders = await self.db.read(
                """
                SELECT o.*, sc.symbol FROM orderbook_orders o
                JOIN symbol_configs sc ON o.symbol_config_id = sc.id
                WHERE o.user_id = $1
                AND o.symbol_config_id = $2
                AND o.status = ANY($3)
                ORDER BY o.created_at DESC
                LIMIT $4
                """,
                user_id,
                self.symbol_config["id"],
                status_values,
                limit,
            )
        else:
            orders = await self.db.read(
                """
                SELECT o.*, sc.symbol FROM orderbook_orders o
                JOIN symbol_configs sc ON o.symbol_config_id = sc.id
                WHERE o.user_id = $1
                AND o.symbol_config_id = $2
                ORDER BY o.created_at DESC
                LIMIT $3
                """,
                user_id,
                self.symbol_config["id"],
                limit,
            )

        return orders
