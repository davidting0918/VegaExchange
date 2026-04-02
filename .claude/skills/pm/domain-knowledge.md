# Crypto Exchange Domain Knowledge

This document provides domain expertise for the VegaExchange PM skill.
VegaExchange is a **trading simulation laboratory** — not a production exchange.
The goal is to let users experiment with market mechanisms and strategies.

---

## 1. Spot Trading (現貨交易)

### CLOB — Central Limit Order Book
- **Price-time priority**: Orders matched by best price first, then earliest time
- **Order types** (common in CEX):
  - **Limit order**: Execute at specified price or better
  - **Market order**: Execute immediately at best available price
  - **Stop-limit**: Triggered when price hits stop level, then becomes limit order
  - **Stop-market**: Triggered when price hits stop level, then becomes market order
  - **IOC (Immediate or Cancel)**: Fill what's available, cancel the rest
  - **FOK (Fill or Kill)**: Fill entirely or cancel entirely
  - **GTC (Good Till Cancel)**: Remains until filled or manually cancelled
  - **Post-only**: Only adds liquidity (maker only), rejected if would match immediately
- **Maker/Taker model**: Makers add liquidity (limit orders resting on book), takers remove it
- **Fee tiers**: Typically tiered by 30-day volume (e.g., Binance VIP levels)
  - Common: Maker 0.02-0.10%, Taker 0.04-0.10%
- **Tick size**: Minimum price increment (e.g., 0.01 USDT)
- **Lot size**: Minimum quantity increment
- **Market data feeds**: L1 (best bid/ask), L2 (order book depth), L3 (individual orders)

### CEX Reference (Binance, OKX, Bybit)
- Unified account systems (spot + margin + futures in one account)
- Sub-accounts for institutional traders
- Cross-margin and isolated margin modes
- Real-time WebSocket streams for order book, trades, klines

---

## 2. AMM — Automated Market Maker (自動做市商)

### Constant Product AMM (x * y = k)
- **VegaExchange current model**: Uses `x * y = k` formula
- Price determined by reserve ratio: `price = reserve_quote / reserve_base`
- **Slippage**: Larger trades move the price more
- **Price impact formula**: `price_impact = trade_size / (reserve + trade_size)`

### Key Concepts
- **Liquidity Pool (LP)**: Token pairs deposited by liquidity providers
- **LP Tokens**: Represent proportional share of the pool
- **Impermanent Loss (IL, 無常損失)**: Loss vs. simply holding when price diverges
  - IL formula: `IL = 2 * sqrt(price_ratio) / (1 + price_ratio) - 1`
  - At 2x price change: ~5.7% IL, at 5x: ~25.5% IL
- **Swap fee**: Typically 0.3% (Uniswap V2), accrues to LPs
- **TWAP (Time-Weighted Average Price)**: Oracle-resistant price feed from AMM

### Advanced AMM Models (for future consideration)
- **Concentrated Liquidity (Uniswap V3)**: LPs provide liquidity in specific price ranges
  - Higher capital efficiency but more complex IL
  - Range orders: liquidity in a single tick = limit order
- **Curve StableSwap**: Optimized for pegged assets (stablecoins)
  - Uses amplification coefficient (A) to flatten the curve near peg
- **Balancer**: Weighted pools (not just 50/50)
- **GMX-style**: Oracle-based pricing, zero price impact for traders, LP = counterparty
- **Hybrid (CLOB + AMM)**: e.g., Serum + Raydium on Solana

### DEX Reference
- **Uniswap**: Pioneer of constant product AMM, V3 introduced concentrated liquidity
- **Curve**: Stablecoin-optimized AMM, veToken governance model
- **Raydium**: Hybrid AMM + CLOB (integrated with Serum order book)
- **Osmosis**: Cosmos-based DEX with customizable bonding curves

---

## 3. Perpetual Futures (永續合約)

### Core Mechanics
- **No expiry date**: Unlike traditional futures, perpetuals never settle
- **Funding rate (資金費率)**: Periodic payment between longs and shorts
  - Purpose: Anchors perpetual price to spot (index) price
  - Formula (simplified): `funding_rate = (perp_price - index_price) / index_price`
  - Typical interval: every 8 hours (Binance), every 1 hour (dYdX)
  - Positive rate: longs pay shorts (perp > index)
  - Negative rate: shorts pay longs (perp < index)
- **Mark price**: Used for liquidation/PnL calculation
  - Usually: weighted average of index price + decaying funding basis
  - Prevents manipulation-triggered liquidations
- **Index price**: Weighted average from multiple spot exchanges

### Margin System (保證金系統)
- **Initial margin (初始保證金)**: Required to open a position
  - `initial_margin = position_size / leverage`
- **Maintenance margin (維持保證金)**: Minimum to keep position open
  - Typically 50% of initial margin (varies by tier)
- **Cross margin**: All available balance used as margin (shared across positions)
- **Isolated margin**: Only allocated amount used as margin (per position)
- **Leverage**: Common range 1x-125x (Binance), typically 1x-50x
- **Margin ratio**: `margin_ratio = maintenance_margin / account_equity`

### Liquidation Engine (清算引擎)
- **Trigger**: When margin ratio falls below maintenance requirement
- **Partial liquidation**: Reduce position incrementally (reduces cascade risk)
- **Full liquidation**: Close entire position at bankruptcy price
- **Insurance fund (保險基金)**: Covers shortfall when liquidation price < bankruptcy price
  - Funded by: profitable liquidations, exchange contributions
- **ADL (Auto-Deleveraging, 自動減倉)**: When insurance fund depleted
  - Opposite-side traders are force-closed based on profit ranking
- **Socialized loss**: Alternative to ADL — spread losses across all traders

### Position Management
- **PnL calculation**:
  - Long: `PnL = (exit_price - entry_price) * quantity`
  - Short: `PnL = (entry_price - exit_price) * quantity`
- **ROE (Return on Equity)**: `ROE = PnL / initial_margin`
- **Unrealized PnL**: Based on mark price (not last traded price)
- **Position sizing**: `max_position = account_equity * leverage`

### CEX Perpetual Reference
- **Binance Futures**: Largest by volume, USDⓈ-M and COIN-M contracts
- **Bybit**: Known for derivatives, linear and inverse perpetuals
- **OKX**: Unified account, portfolio margin
- **dYdX**: Decentralized perpetual exchange (order book based, on own chain)
- **GMX**: DEX perpetuals using multi-asset pool (GLP) as counterparty
- **Hyperliquid**: On-chain order book perpetuals with sub-second latency

---

## 4. Market-Making Strategies (做市策略)

### Basic Strategies
- **Grid trading (網格交易)**: Place orders at fixed intervals above and below current price
  - Arithmetic grid: equal price spacing
  - Geometric grid: equal percentage spacing
- **Spread quoting**: Maintain bid-ask spread around fair value
  - Adjust width based on volatility
- **Inventory management**: Skew quotes to reduce net position

### Advanced Strategies
- **Mean reversion (均值回歸)**: Trade when price deviates from moving average
  - VegaExchange already has `mean_reversion_trader.py`
- **Statistical arbitrage**: Exploit price discrepancies between correlated assets
- **Basis trading**: Exploit funding rate between perp and spot
  - Cash-and-carry: Long spot + short perp when funding is positive
- **Delta-neutral LP**: Hedge AMM LP position with perp short
  - Eliminates IL by maintaining delta-neutral exposure
- **Avellaneda-Stoikov model**: Optimal bid-ask spread based on:
  - Inventory risk aversion (γ)
  - Volatility (σ)
  - Time horizon (T)
  - Formula: `reservation_price = mid_price - q * γ * σ² * (T - t)`

### Simulation Considerations
- **Backtesting**: Run strategies against historical data
- **Paper trading**: Real-time simulation without real assets
- **Monte Carlo simulation**: Generate random price paths for stress testing
- **Metrics**: Sharpe ratio, max drawdown, PnL, fill rate, inventory turnover
- **Latency modeling**: Simulate realistic order placement/cancellation delays
- **Slippage modeling**: Account for market impact in backtests

---

## 5. Oracle System (預言機系統)

### Purpose
- Provide reliable external price data for mark price, liquidation, settlement
- Critical for perpetual futures and any DeFi-style feature

### Approaches
- **Multi-source median**: Aggregate prices from N exchanges, take median
- **TWAP from AMM**: Use on-chain AMM prices with time weighting
- **Chainlink-style**: Decentralized oracle network with economic guarantees
- **Pyth Network**: Low-latency oracle designed for DeFi
- **Band Protocol**: Cross-chain oracle solution

### For VegaExchange Simulation
- Can simulate oracle feeds with configurable:
  - Update frequency
  - Price deviation thresholds
  - Staleness detection
  - Manipulation scenarios (to test robustness)

---

## 6. Risk Management (風險管理)

### Position Limits
- Per-user position limits (by tier)
- Open interest caps per market
- Concentration limits (max % of total open interest)

### Circuit Breakers
- Price band limits (e.g., ±10% from index in 5 minutes)
- Trading halt on extreme volatility
- Maximum order size limits

### System Risk
- Insurance fund adequacy monitoring
- ADL queue management
- Real-time risk metric dashboards

---

## 7. Fee Structure (費用結構)

### Common Fee Models
| Type | Typical Range | Notes |
|------|---------------|-------|
| Spot maker | 0.02-0.10% | Lower = incentivizes liquidity |
| Spot taker | 0.04-0.10% | Higher = cost of immediacy |
| Perp maker | 0.00-0.02% | Often zero or negative (rebate) |
| Perp taker | 0.03-0.06% | Main revenue source |
| Swap fee (AMM) | 0.05-1.00% | Accrues to LPs |
| Funding rate | Variable | Not a fee — transfer between traders |
| Withdrawal | Fixed or % | Per-asset basis |

### VIP Tiers
- Volume-based: 30-day trading volume thresholds
- Token-based: Hold exchange token for discounts (e.g., BNB on Binance)
- Market-maker programs: Special rates for qualified MMs

---

## 8. Architecture Patterns for Exchange Simulation

### Event-Driven Architecture
- Order events → matching engine → trade events → settlement
- Useful for replay and backtesting

### State Machine for Orders
```
NEW → PARTIALLY_FILLED → FILLED
NEW → CANCELLED
NEW → EXPIRED (for GTT orders)
NEW → REJECTED
```

### Performance Considerations for Simulation
- In-memory order book for speed
- Async trade recording (don't block matching)
- Snapshot/restore for simulation replay
- Configurable latency injection
