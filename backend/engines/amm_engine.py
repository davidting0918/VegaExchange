"""
AMM (Automated Market Maker) Engine

Implements constant product formula: x * y = k
"""

from decimal import Decimal
from math import sqrt
from typing import Any, Dict, Optional

from backend.engines.base_engine import BaseEngine, QuoteResult, TradeResult
from backend.models.enums import EngineType, OrderSide, TradeStatus


class AMMEngine(BaseEngine):
    """
    Automated Market Maker engine using constant product formula.

    Formula: reserve_base * reserve_quote = k (constant)

    When a user swaps:
    - Buy base: User gives quote asset, receives base asset
    - Sell base: User gives base asset, receives quote asset
    """

    @property
    def engine_type(self) -> EngineType:
        return EngineType.AMM

    async def _get_pool(self) -> Optional[Dict[str, Any]]:
        """Get the AMM pool for this symbol"""
        return await self.db.read_one(
            """
            SELECT * FROM amm_pools
            WHERE symbol_id = $1
            """,
            self.symbol_config["symbol_id"],
        )

    async def _update_pool(
        self,
        reserve_base_delta: Decimal,
        reserve_quote_delta: Decimal,
        volume_base: Decimal,
        volume_quote: Decimal,
        fees_collected: Decimal,
    ) -> bool:
        """Update pool reserves and statistics"""
        result = await self.db.execute(
            """
            UPDATE amm_pools
            SET reserve_base = reserve_base + $2,
                reserve_quote = reserve_quote + $3,
                k_value = (reserve_base + $2) * (reserve_quote + $3),
                total_volume_base = total_volume_base + $4,
                total_volume_quote = total_volume_quote + $5,
                total_fees_collected = total_fees_collected + $6,
                updated_at = NOW()
            WHERE symbol_id = $1
            AND reserve_base + $2 >= 0
            AND reserve_quote + $3 >= 0
            """,
            self.symbol_config["symbol_id"],
            reserve_base_delta,
            reserve_quote_delta,
            volume_base,
            volume_quote,
            fees_collected,
        )
        return "UPDATE 1" in result

    def _calculate_output_amount(
        self,
        input_amount: Decimal,
        input_reserve: Decimal,
        output_reserve: Decimal,
        fee_rate: Decimal,
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate output amount using constant product formula.

        Formula:
        (input_reserve + input_amount_with_fee) * (output_reserve - output_amount) = k
        output_amount = output_reserve - k / (input_reserve + input_amount_with_fee)

        Simplified (applying fee to input):
        input_amount_with_fee = input_amount * (1 - fee_rate)
        output_amount = output_reserve * input_amount_with_fee / (input_reserve + input_amount_with_fee)

        Returns:
            Tuple of (output_amount, fee_amount)
        """
        fee_amount = input_amount * fee_rate
        input_amount_after_fee = input_amount - fee_amount

        # Constant product formula
        output_amount = (output_reserve * input_amount_after_fee) / (input_reserve + input_amount_after_fee)

        return output_amount, fee_amount

    def _calculate_price_impact(
        self,
        input_amount: Decimal,
        input_reserve: Decimal,
        output_reserve: Decimal,
    ) -> Decimal:
        """
        Calculate price impact as a percentage.

        Price impact = (execution_price - spot_price) / spot_price * 100
        """
        if input_reserve == 0 or output_reserve == 0:
            return Decimal("100")

        spot_price = output_reserve / input_reserve
        output_amount = (output_reserve * input_amount) / (input_reserve + input_amount)
        execution_price = input_amount / output_amount if output_amount > 0 else Decimal("0")

        if spot_price == 0:
            return Decimal("100")

        price_impact = abs((execution_price - spot_price) / spot_price) * 100
        return price_impact

    async def execute_trade(
        self,
        user_id: str,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        price: Optional[Decimal] = None,
        min_amount_out: Optional[Decimal] = None,
        **kwargs,
    ) -> TradeResult:
        """
        Execute an AMM swap.

        For BUY (buy base asset):
            - User specifies quote_amount (USDT to spend)
            - User receives base asset (e.g., BTC)

        For SELL (sell base asset):
            - User specifies quantity (base asset to sell)
            - User receives quote asset (e.g., USDT)
        """
        # Get pool
        pool = await self._get_pool()
        if not pool:
            return TradeResult(
                success=False,
                error_message=f"No AMM pool found for {self.symbol}",
            )

        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))
        fee_rate = Decimal(str(pool["fee_rate"]))

        # Determine input/output based on side
        if side == OrderSide.BUY:
            # Buying base asset with quote asset
            if quote_amount is None:
                return TradeResult(
                    success=False,
                    error_message="quote_amount is required for AMM buy",
                )

            input_amount = quote_amount
            input_asset = self.quote_asset
            input_reserve = reserve_quote
            output_reserve = reserve_base
            output_asset = self.base_asset

        else:  # SELL
            # Selling base asset for quote asset
            if quantity is None:
                return TradeResult(
                    success=False,
                    error_message="quantity is required for AMM sell",
                )

            input_amount = quantity
            input_asset = self.base_asset
            input_reserve = reserve_base
            output_reserve = reserve_quote
            output_asset = self.quote_asset

        # Check user balance
        if not await self.validate_balance(user_id, input_asset, input_amount):
            return TradeResult(
                success=False,
                error_message=f"Insufficient {input_asset} balance",
            )

        # Calculate output
        output_amount, fee_amount = self._calculate_output_amount(
            input_amount,
            input_reserve,
            output_reserve,
            fee_rate,
        )

        # Check slippage protection
        if min_amount_out is not None and output_amount < min_amount_out:
            return TradeResult(
                success=False,
                error_message=f"Slippage too high: would receive {output_amount}, minimum {min_amount_out}",
            )

        # Calculate price impact
        price_impact = self._calculate_price_impact(
            input_amount - fee_amount,  # Use amount after fee for price impact
            input_reserve,
            output_reserve,
        )

        # Calculate execution price
        if side == OrderSide.BUY:
            exec_quantity = output_amount  # Base asset received
            exec_quote_amount = input_amount  # Quote asset spent
            exec_price = exec_quote_amount / exec_quantity if exec_quantity > 0 else Decimal("0")
        else:
            exec_quantity = input_amount  # Base asset sold
            exec_quote_amount = output_amount  # Quote asset received
            exec_price = exec_quote_amount / exec_quantity if exec_quantity > 0 else Decimal("0")

        # Update user balances
        # Deduct input asset
        if not await self.update_balance(user_id, input_asset, -input_amount):
            return TradeResult(
                success=False,
                error_message=f"Failed to deduct {input_asset} balance",
            )

        # Add output asset
        if not await self.update_balance(user_id, output_asset, output_amount):
            # Rollback input deduction
            await self.update_balance(user_id, input_asset, input_amount)
            return TradeResult(
                success=False,
                error_message=f"Failed to add {output_asset} balance",
            )

        # Update pool reserves
        if side == OrderSide.BUY:
            # User bought base: pool loses base, gains quote
            reserve_base_delta = -output_amount
            reserve_quote_delta = input_amount
        else:
            # User sold base: pool gains base, loses quote
            reserve_base_delta = input_amount
            reserve_quote_delta = -output_amount

        if not await self._update_pool(
            reserve_base_delta,
            reserve_quote_delta,
            abs(reserve_base_delta),
            abs(reserve_quote_delta),
            fee_amount,
        ):
            # Rollback balance changes
            await self.update_balance(user_id, input_asset, input_amount)
            await self.update_balance(user_id, output_asset, -output_amount)
            return TradeResult(
                success=False,
                error_message="Failed to update pool reserves",
            )

        # Record trade
        trade_id = await self.record_trade(
            user_id=user_id,
            side=side,
            price=exec_price,
            quantity=exec_quantity,
            quote_amount=exec_quote_amount,
            fee_amount=fee_amount,
            fee_asset=input_asset,
            status=TradeStatus.COMPLETED,
            engine_data={
                "input_amount": float(input_amount),
                "output_amount": float(output_amount),
                "price_impact": float(price_impact),
                "reserve_base_after": float(reserve_base + reserve_base_delta),
                "reserve_quote_after": float(reserve_quote + reserve_quote_delta),
            },
        )

        return TradeResult(
            success=True,
            trade_id=trade_id,
            symbol=self.symbol,
            side=side,
            engine_type=EngineType.AMM,
            price=exec_price,
            quantity=exec_quantity,
            quote_amount=exec_quote_amount,
            fee_amount=fee_amount,
            fee_asset=input_asset,
            status=TradeStatus.COMPLETED,
            engine_data={
                "input_amount": input_amount,
                "output_amount": output_amount,
                "price_impact": price_impact,
            },
        )

    async def get_quote(
        self,
        side: OrderSide,
        quantity: Optional[Decimal] = None,
        quote_amount: Optional[Decimal] = None,
        **kwargs,
    ) -> QuoteResult:
        """Get a quote for a potential swap"""
        pool = await self._get_pool()
        if not pool:
            return QuoteResult(
                success=False,
                error_message=f"No AMM pool found for {self.symbol}",
            )

        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))
        fee_rate = Decimal(str(pool["fee_rate"]))

        if side == OrderSide.BUY:
            if quote_amount is None:
                return QuoteResult(
                    success=False,
                    error_message="quote_amount is required for buy quote",
                )

            input_amount = quote_amount
            input_asset = self.quote_asset
            input_reserve = reserve_quote
            output_reserve = reserve_base
            output_asset = self.base_asset
        else:
            if quantity is None:
                return QuoteResult(
                    success=False,
                    error_message="quantity is required for sell quote",
                )

            input_amount = quantity
            input_asset = self.base_asset
            input_reserve = reserve_base
            output_reserve = reserve_quote
            output_asset = self.quote_asset

        output_amount, fee_amount = self._calculate_output_amount(
            input_amount,
            input_reserve,
            output_reserve,
            fee_rate,
        )

        price_impact = self._calculate_price_impact(
            input_amount - fee_amount,
            input_reserve,
            output_reserve,
        )

        effective_price = input_amount / output_amount if output_amount > 0 else Decimal("0")

        return QuoteResult(
            success=True,
            input_amount=input_amount,
            input_asset=input_asset,
            output_amount=output_amount,
            output_asset=output_asset,
            effective_price=effective_price,
            price_impact=price_impact,
            fee_amount=fee_amount,
            fee_asset=input_asset,
            slippage=price_impact,
        )

    async def get_market_data(self) -> Dict[str, Any]:
        """Get current market data for AMM pool"""
        pool = await self._get_pool()
        if not pool:
            return {
                "symbol": self.symbol,
                "engine_type": EngineType.AMM.value,
                "error": "Pool not found",
            }

        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))

        current_price = reserve_quote / reserve_base if reserve_base > 0 else Decimal("0")

        return {
            "symbol": self.symbol,
            "engine_type": EngineType.AMM.value,
            "current_price": float(current_price),
            "reserve_base": float(reserve_base),
            "reserve_quote": float(reserve_quote),
            "k_value": float(pool["k_value"]),
            "fee_rate": float(pool["fee_rate"]),
            "total_volume_base": float(pool["total_volume_base"]),
            "total_volume_quote": float(pool["total_volume_quote"]),
            "total_fees_collected": float(pool["total_fees_collected"]),
        }

    async def _get_lp_position(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get LP position for a user"""
        pool = await self._get_pool()
        if not pool:
            return None

        return await self.db.read_one(
            """
            SELECT * FROM lp_positions
            WHERE pool_id = $1 AND user_id = $2
            """,
            pool["pool_id"],
            user_id,
        )

    async def add_liquidity(
        self,
        user_id: str,
        base_amount: Decimal,
        quote_amount: Decimal,
    ) -> Dict[str, Any]:
        """
        Add liquidity to the AMM pool.

        Args:
            user_id: User ID adding liquidity
            base_amount: Amount of base asset to add
            quote_amount: Amount of quote asset to add

        Returns:
            Dictionary with success status, lp_shares, and pool info
        """
        # Get pool
        pool = await self._get_pool()
        if not pool:
            return {
                "success": False,
                "error": f"No AMM pool found for {self.symbol}",
            }

        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))
        total_lp_shares = Decimal(str(pool["total_lp_shares"]))

        # Validate balances
        if not await self.validate_balance(user_id, self.base_asset, base_amount):
            return {
                "success": False,
                "error": f"Insufficient {self.base_asset} balance",
            }

        if not await self.validate_balance(user_id, self.quote_asset, quote_amount):
            return {
                "success": False,
                "error": f"Insufficient {self.quote_asset} balance",
            }

        # Calculate LP shares
        if total_lp_shares == 0:
            # First liquidity provider: LP shares = sqrt(base * quote)
            lp_shares = Decimal(str(sqrt(float(base_amount * quote_amount))))
        else:
            # Calculate shares based on current pool ratio
            # Ensure user provides assets in correct ratio
            current_ratio = reserve_quote / reserve_base if reserve_base > 0 else Decimal("0")
            user_ratio = quote_amount / base_amount if base_amount > 0 else Decimal("0")

            # Allow 0.1% tolerance for ratio mismatch
            ratio_tolerance = Decimal("0.001")
            if abs(user_ratio - current_ratio) / current_ratio > ratio_tolerance if current_ratio > 0 else True:
                return {
                    "success": False,
                    "error": f"Ratio mismatch. Pool ratio: {current_ratio:.6f}, provided ratio: {user_ratio:.6f}",
                }

            # Calculate LP shares based on proportion
            share_base = (base_amount / reserve_base) * total_lp_shares
            share_quote = (quote_amount / reserve_quote) * total_lp_shares
            lp_shares = min(share_base, share_quote)  # Take minimum to prevent over-issuance

        # Deduct user balances
        if not await self.update_balance(user_id, self.base_asset, -base_amount):
            return {
                "success": False,
                "error": f"Failed to deduct {self.base_asset} balance",
            }

        if not await self.update_balance(user_id, self.quote_asset, -quote_amount):
            # Rollback base deduction
            await self.update_balance(user_id, self.base_asset, base_amount)
            return {
                "success": False,
                "error": f"Failed to deduct {self.quote_asset} balance",
            }

        # Update pool reserves
        new_reserve_base = reserve_base + base_amount
        new_reserve_quote = reserve_quote + quote_amount
        new_k_value = new_reserve_base * new_reserve_quote
        new_total_lp_shares = total_lp_shares + lp_shares

        pool_update_result = await self.db.execute(
            """
            UPDATE amm_pools
            SET reserve_base = $2,
                reserve_quote = $3,
                k_value = $4,
                total_lp_shares = $5,
                updated_at = NOW()
            WHERE pool_id = $1
            """,
            pool["pool_id"],
            new_reserve_base,
            new_reserve_quote,
            new_k_value,
            new_total_lp_shares,
        )

        if "UPDATE 1" not in pool_update_result:
            # Rollback balance changes
            await self.update_balance(user_id, self.base_asset, base_amount)
            await self.update_balance(user_id, self.quote_asset, quote_amount)
            return {
                "success": False,
                "error": "Failed to update pool reserves",
            }

        # Update or create LP position
        existing_position = await self._get_lp_position(user_id)
        if existing_position:
            # Update existing position
            await self.db.execute(
                """
                UPDATE lp_positions
                SET lp_shares = lp_shares + $3,
                    updated_at = NOW()
                WHERE pool_id = $1 AND user_id = $2
                """,
                pool["pool_id"],
                user_id,
                lp_shares,
            )
        else:
            # Create new position (SERIAL id is auto-generated)
            await self.db.execute(
                """
                INSERT INTO lp_positions (pool_id, user_id, lp_shares, initial_base_amount, initial_quote_amount)
                VALUES ($1, $2, $3, $4, $5)
                """,
                pool["pool_id"],
                user_id,
                lp_shares,
                base_amount,
                quote_amount,
            )

        # Log the add event to lp_events
        await self.db.execute(
            """
            INSERT INTO lp_events 
            (pool_id, user_id, event_type, lp_shares, base_amount, quote_amount,
             pool_reserve_base, pool_reserve_quote, pool_total_lp_shares)
            VALUES ($1, $2, 'add', $3, $4, $5, $6, $7, $8)
            """,
            pool["pool_id"],
            user_id,
            lp_shares,
            base_amount,
            quote_amount,
            new_reserve_base,
            new_reserve_quote,
            new_total_lp_shares,
        )

        # Create/update LP token balance in user_balances
        lp_token_currency = f"LP-{self.symbol}"
        await self.ensure_balance_exists(user_id, lp_token_currency, account_type="spot")
        
        # Update LP token balance with the new shares
        if not await self.update_balance(user_id, lp_token_currency, lp_shares):
            # If update fails, rollback everything
            await self.update_balance(user_id, self.base_asset, base_amount)
            await self.update_balance(user_id, self.quote_asset, quote_amount)
            # Rollback pool update
            await self.db.execute(
                """
                UPDATE amm_pools
                SET reserve_base = $2,
                    reserve_quote = $3,
                    k_value = $4,
                    total_lp_shares = $5,
                    updated_at = NOW()
                WHERE pool_id = $1
                """,
                pool["pool_id"],
                reserve_base,
                reserve_quote,
                reserve_base * reserve_quote,
                total_lp_shares,
            )
            # Rollback LP position
            if existing_position:
                await self.db.execute(
                    """
                    UPDATE lp_positions
                    SET lp_shares = lp_shares - $3,
                        updated_at = NOW()
                    WHERE pool_id = $1 AND user_id = $2
                    """,
                    pool["pool_id"],
                    user_id,
                    lp_shares,
                )
            else:
                await self.db.execute(
                    """
                    DELETE FROM lp_positions WHERE pool_id = $1 AND user_id = $2
                    """,
                    pool["pool_id"],
                    user_id,
                )
            return {
                "success": False,
                "error": "Failed to update LP token balance",
            }

        return {
            "success": True,
            "lp_shares": float(lp_shares),
            "pool_id": pool["pool_id"],
            "reserve_base": float(new_reserve_base),
            "reserve_quote": float(new_reserve_quote),
            "total_lp_shares": float(new_total_lp_shares),
        }

    async def remove_liquidity(
        self,
        user_id: str,
        lp_shares: Decimal,
    ) -> Dict[str, Any]:
        """
        Remove liquidity from the AMM pool.

        Args:
            user_id: User ID removing liquidity
            lp_shares: Amount of LP shares to burn

        Returns:
            Dictionary with success status, base_out, quote_out, and pool info
        """
        # Get pool
        pool = await self._get_pool()
        if not pool:
            return {
                "success": False,
                "error": f"No AMM pool found for {self.symbol}",
            }

        # Get user's LP position
        position = await self._get_lp_position(user_id)
        if not position:
            return {
                "success": False,
                "error": "No LP position found for user",
            }

        user_lp_shares = Decimal(str(position["lp_shares"]))
        if lp_shares > user_lp_shares:
            return {
                "success": False,
                "error": f"Insufficient LP shares. You have {user_lp_shares}, requested {lp_shares}",
            }

        reserve_base = Decimal(str(pool["reserve_base"]))
        reserve_quote = Decimal(str(pool["reserve_quote"]))
        total_lp_shares = Decimal(str(pool["total_lp_shares"]))

        if total_lp_shares == 0:
            return {
                "success": False,
                "error": "Pool has no LP shares",
            }

        # Calculate assets to return
        share_ratio = lp_shares / total_lp_shares
        base_out = reserve_base * share_ratio
        quote_out = reserve_quote * share_ratio

        # Update pool reserves
        new_reserve_base = reserve_base - base_out
        new_reserve_quote = reserve_quote - quote_out
        new_k_value = new_reserve_base * new_reserve_quote
        new_total_lp_shares = total_lp_shares - lp_shares

        # Ensure reserves don't go negative
        if new_reserve_base < 0 or new_reserve_quote < 0:
            return {
                "success": False,
                "error": "Insufficient pool reserves",
            }

        pool_update_result = await self.db.execute(
            """
            UPDATE amm_pools
            SET reserve_base = $2,
                reserve_quote = $3,
                k_value = $4,
                total_lp_shares = $5,
                updated_at = NOW()
            WHERE pool_id = $1
            """,
            pool["pool_id"],
            new_reserve_base,
            new_reserve_quote,
            new_k_value,
            new_total_lp_shares,
        )

        if "UPDATE 1" not in pool_update_result:
            return {
                "success": False,
                "error": "Failed to update pool reserves",
            }

        # Update user balances
        if not await self.update_balance(user_id, self.base_asset, base_out):
            # Rollback pool update would be complex, so we'll just return error
            return {
                "success": False,
                "error": f"Failed to add {self.base_asset} balance",
            }

        if not await self.update_balance(user_id, self.quote_asset, quote_out):
            # Rollback base balance
            await self.update_balance(user_id, self.base_asset, -base_out)
            return {
                "success": False,
                "error": f"Failed to add {self.quote_asset} balance",
            }

        # Update LP position
        new_user_lp_shares = user_lp_shares - lp_shares
        if new_user_lp_shares <= 0:
            # Delete position if all shares removed
            await self.db.execute(
                """
                DELETE FROM lp_positions WHERE pool_id = $1 AND user_id = $2
                """,
                pool["pool_id"],
                user_id,
            )
        else:
            # Update position
            await self.db.execute(
                """
                UPDATE lp_positions
                SET lp_shares = $3,
                    updated_at = NOW()
                WHERE pool_id = $1 AND user_id = $2
                """,
                pool["pool_id"],
                user_id,
                new_user_lp_shares,
            )

        # Log the remove event to lp_events
        await self.db.execute(
            """
            INSERT INTO lp_events 
            (pool_id, user_id, event_type, lp_shares, base_amount, quote_amount,
             pool_reserve_base, pool_reserve_quote, pool_total_lp_shares)
            VALUES ($1, $2, 'remove', $3, $4, $5, $6, $7, $8)
            """,
            pool["pool_id"],
            user_id,
            lp_shares,
            base_out,
            quote_out,
            new_reserve_base,
            new_reserve_quote,
            new_total_lp_shares,
        )

        # Update LP token balance (deduct burned shares)
        lp_token_currency = f"LP-{self.symbol}"
        if not await self.update_balance(user_id, lp_token_currency, -lp_shares):
            # If update fails, rollback everything
            await self.update_balance(user_id, self.base_asset, -base_out)
            await self.update_balance(user_id, self.quote_asset, -quote_out)
            # Rollback pool update
            await self.db.execute(
                """
                UPDATE amm_pools
                SET reserve_base = $2,
                    reserve_quote = $3,
                    k_value = $4,
                    total_lp_shares = $5,
                    updated_at = NOW()
                WHERE pool_id = $1
                """,
                pool["pool_id"],
                reserve_base,
                reserve_quote,
                reserve_base * reserve_quote,
                total_lp_shares,
            )
            # Rollback LP position
            await self.db.execute(
                """
                UPDATE lp_positions
                SET lp_shares = $3,
                    updated_at = NOW()
                WHERE pool_id = $1 AND user_id = $2
                """,
                pool["pool_id"],
                user_id,
                user_lp_shares,
            )
            return {
                "success": False,
                "error": "Failed to update LP token balance",
            }

        return {
            "success": True,
            "base_out": float(base_out),
            "quote_out": float(quote_out),
            "lp_shares_burned": float(lp_shares),
            "remaining_lp_shares": float(new_user_lp_shares) if new_user_lp_shares > 0 else 0,
            "pool_id": pool["pool_id"],
            "reserve_base": float(new_reserve_base),
            "reserve_quote": float(new_reserve_quote),
            "total_lp_shares": float(new_total_lp_shares),
        }
