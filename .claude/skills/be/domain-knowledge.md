# Senior Backend Engineer — Domain Knowledge

Deep technical knowledge for building exchange-grade backend systems.
This document covers **implementation patterns**, not product concepts
(product-level domain knowledge lives in the `/pm` skill).

---

## 1. Order Matching Engine Design

### Price-Time Priority (CLOB)
```
Matching algorithm:
1. Incoming order arrives (buy or sell)
2. Check opposing side of book for matchable prices
   - Buy order: match against asks where ask_price <= buy_price
   - Sell order: match against bids where bid_price >= sell_price
3. Match in price priority (best price first), then time priority (FIFO)
4. For each match:
   a. Determine fill quantity: min(incoming_remaining, resting_remaining)
   b. Execute at resting order's price (price improvement for aggressor)
   c. Update both orders' filled quantities
   d. Record trade
   e. Settle balances atomically
5. If incoming order has remaining quantity:
   - LIMIT: rest on book
   - MARKET: cancel remaining (or reject if no fills)
   - IOC: cancel remaining
   - FOK: would have been rejected in step 2 if not fully fillable
```

### Critical Implementation Details
- **Atomicity**: The entire match cycle (match → trade → settle) must be in ONE transaction
- **Locking order**: Always lock in consistent order to prevent deadlocks
  - Lock by: user_id ASC, then asset ASC
- **Self-trade prevention**: Skip matching if maker_user_id == taker_user_id
- **Minimum order size**: Enforce minimum notional value to prevent dust orders

### In-Memory vs Database Matching
| Approach | Pros | Cons |
|----------|------|------|
| **In-memory book** | Sub-ms latency, high throughput | Recovery complexity, state sync |
| **Database-only** | Crash-safe, simple | Higher latency (~5-50ms per match) |
| **Hybrid** | Best of both | Complex consistency management |

**VegaExchange recommendation**: Database-only is fine for simulation. Optimize later if needed.

---

## 2. Balance & Settlement System

### Double-Entry Bookkeeping
Every trade must have balanced entries:
```
Buy 1 BTC @ 50000 USDT:
  Buyer:  USDT -50000 (available), BTC +1 (available)
  Seller: BTC -1 (locked→removed), USDT +50000 (available)
```

### Balance Locking Flow (CLOB)
```
Place buy order (1 BTC @ 50000):
  1. Check: available_USDT >= 50000
  2. Lock:  available_USDT -= 50000, locked_USDT += 50000

Order filled:
  3. Settle: locked_USDT -= 50000 (buyer)
             available_BTC += 1 (buyer)
             locked_BTC -= 1 (seller, was locked when their sell order placed)
             available_USDT += 50000 (seller)

Order cancelled:
  3. Unlock: locked_USDT -= 50000, available_USDT += 50000
```

### Race Condition Prevention
```sql
-- Use SELECT FOR UPDATE to lock the balance row
BEGIN;
SELECT available, locked FROM user_balances
  WHERE user_id = $1 AND currency = $2
  FOR UPDATE;

-- Check sufficient balance
-- Update balance
-- Commit
COMMIT;
```

### Partial Fill Handling
- Track `filled_quantity` and `remaining_quantity` on orders
- Each partial fill: create separate trade record, settle proportional amounts
- When fully filled: update order status to FILLED
- Fee calculated per fill, not per order

---

## 3. AMM Implementation Patterns

### Constant Product Invariant
```
x * y = k (before fees)

Swap dx of token X for dy of token Y:
  dy = y - k / (x + dx_after_fee)
  dx_after_fee = dx * (1 - fee_rate)

Price impact:
  price_before = y / x
  price_after = (y - dy) / (x + dx)
  impact = (price_after - price_before) / price_before
```

### Liquidity Operations
```
Add liquidity (proportional):
  ratio = deposit_x / reserve_x  (must equal deposit_y / reserve_y)
  new_lp_tokens = total_lp_supply * ratio

Remove liquidity:
  share = lp_tokens_burned / total_lp_supply
  withdraw_x = reserve_x * share
  withdraw_y = reserve_y * share
```

### Edge Cases
- **First liquidity provider**: Sets initial price, gets sqrt(x*y) LP tokens
- **Single-sided deposit**: Must swap half first (or use Zap pattern)
- **Minimum liquidity**: Lock small amount of LP tokens to prevent empty pool
- **Reentrancy**: Not a concern in backend, but good practice to update state before external calls

---

## 4. Perpetual Futures Engine

### Position Data Model
```sql
CREATE TABLE positions (
    position_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    symbol_id INTEGER NOT NULL,
    side INTEGER NOT NULL,          -- 0=LONG, 1=SHORT
    entry_price DECIMAL NOT NULL,
    quantity DECIMAL NOT NULL,
    leverage DECIMAL NOT NULL,
    margin DECIMAL NOT NULL,         -- isolated margin amount
    unrealized_pnl DECIMAL DEFAULT 0,
    realized_pnl DECIMAL DEFAULT 0,
    liquidation_price DECIMAL,
    margin_type INTEGER DEFAULT 0,   -- 0=ISOLATED, 1=CROSS
    status INTEGER DEFAULT 0,        -- 0=OPEN, 1=CLOSED, 2=LIQUIDATED
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### PnL Calculation
```python
# Long position
unrealized_pnl = (mark_price - entry_price) * quantity
# Short position
unrealized_pnl = (entry_price - mark_price) * quantity

# ROE (Return on Equity)
roe = unrealized_pnl / margin

# Margin ratio
margin_ratio = (margin + unrealized_pnl) / (quantity * mark_price)
```

### Liquidation Logic
```python
# Liquidation trigger
if margin_ratio <= maintenance_margin_rate:
    liquidate(position)

# Liquidation price (isolated, long)
liq_price = entry_price * (1 - 1/leverage + maintenance_margin_rate)

# Liquidation price (isolated, short)
liq_price = entry_price * (1 + 1/leverage - maintenance_margin_rate)
```

### Funding Rate Implementation
```python
# Every funding interval (e.g., 8 hours):
funding_rate = clamp(
    (perp_twap - index_twap) / index_twap,
    -0.75%, +0.75%
)

# Settlement:
for position in open_positions:
    funding_payment = position.quantity * mark_price * funding_rate
    if position.side == LONG:
        position.margin -= funding_payment  # positive rate: longs pay
    else:
        position.margin += funding_payment  # positive rate: shorts receive
```

### Mark Price
```python
# Prevent manipulation-based liquidations
mark_price = index_price + decaying_ema(perp_price - index_price)

# Simple version for simulation:
mark_price = (index_price * 0.5) + (last_trade_price * 0.5)
```

---

## 5. Massive System Design Patterns

### Connection Pool Tuning
```python
# Current: min=1, max=50
# Recommendation per workload:
#   Read-heavy: max=100, min=10
#   Write-heavy: max=50, min=5 (writes hold locks longer)
#   Mixed: max=50, min=5 (current is fine)
```

### Transaction Isolation Levels
| Level | Use Case | Trade-off |
|-------|----------|-----------|
| READ COMMITTED | Default queries | Phantom reads possible |
| REPEATABLE READ | Balance checks | Serialization errors on conflict |
| SERIALIZABLE | Critical financial ops | Highest conflict rate, retry needed |

**Recommendation**: Use READ COMMITTED by default, SERIALIZABLE for balance mutations.

### Async Processing Pattern
```
API Request → Validate → Queue → Process → Respond

For VegaExchange simulation, direct processing is fine.
Queue pattern needed only if:
- Throughput exceeds DB connection pool capacity
- Need guaranteed ordering (e.g., order matching)
- Need retry/dead-letter for failed operations
```

### Caching Strategy
```
Hot data (cache in engine instances):
- Order book top-of-book
- AMM pool reserves
- Symbol configs

Warm data (cache with TTL):
- Market data aggregations
- User balance snapshots

Cold data (always from DB):
- Trade history
- Position details
- Audit logs
```

### WebSocket Architecture (future)
```
Client ←→ WebSocket Server ←→ Event Bus ←→ Engine

Channels:
- orderbook:{symbol}    — L2 book updates (bid/ask depth)
- trades:{symbol}       — Real-time trade stream
- ticker:{symbol}       — 24h stats, last price
- user:{user_id}        — Balance changes, order updates, fills

Implementation options:
1. FastAPI WebSocket + asyncio queues (simplest, good for simulation)
2. Redis Pub/Sub as event bus (scales to multiple workers)
3. Kafka/NATS for production-grade (overkill for simulation)
```

---

## 6. API Design for Exchange Systems

### Rate Limiting Pattern
```python
# Tiered rate limits (per API key or user)
RATE_LIMITS = {
    "default":    {"requests": 1200, "orders": 100, "window": 60},  # per minute
    "vip1":       {"requests": 2400, "orders": 200, "window": 60},
    "market_maker": {"requests": 6000, "orders": 500, "window": 60},
}

# Implementation: sliding window counter in Redis or PostgreSQL
```

### Pagination Pattern
```python
# Cursor-based (preferred for real-time data)
GET /api/trades?symbol=BTC-USDT&after=1234567890123&limit=100

# Offset-based (simpler, fine for simulation)
GET /api/trades?symbol=BTC-USDT&offset=0&limit=100
```

### API Response Envelope
```python
# Existing VegaExchange pattern — maintain consistency
{
    "success": true,
    "data": { ... },
    "error": null
}

# Error response
{
    "success": false,
    "data": null,
    "error": {
        "code": "INSUFFICIENT_BALANCE",
        "message": "Not enough USDT available"
    }
}
```

### Decimal Serialization
```python
# Always serialize decimals as strings in JSON to prevent precision loss
# Current VegaExchange converts Decimal→float (acceptable for simulation)
# Production would use string representation: "price": "50000.00"
```

---

## 7. Database Migration Patterns

### For VegaExchange (Playground/Staging)
Since this is a simulation environment, schema changes can be applied directly:

```sql
-- Safe pattern: add new column with default
ALTER TABLE orders ADD COLUMN leverage DECIMAL DEFAULT 1.0;

-- Safe pattern: add new table
CREATE TABLE IF NOT EXISTS positions (...);

-- Destructive but OK for playground:
DROP TABLE IF EXISTS old_table CASCADE;
TRUNCATE TABLE trades;  -- clear test data if schema incompatible
```

### Index Strategy
```sql
-- Add indexes for query patterns:
-- 1. User's open orders (frequent query)
CREATE INDEX idx_orders_user_open ON orderbook_orders(user_id, status)
  WHERE status IN (0, 1);  -- OPEN or PARTIAL

-- 2. Trade history by symbol and time
CREATE INDEX idx_trades_symbol_time ON trades(symbol_id, created_at DESC);

-- 3. User balances lookup
CREATE INDEX idx_balances_user ON user_balances(user_id);

-- 4. Positions by user (future)
CREATE INDEX idx_positions_user_open ON positions(user_id)
  WHERE status = 0;  -- OPEN only
```

---

## 8. Error Codes for Exchange Systems

### Standard Error Code System
```python
# Organize by category
ERROR_CODES = {
    # Balance errors (1xxx)
    "INSUFFICIENT_BALANCE": 1001,
    "BALANCE_LOCKED": 1002,
    "INVALID_AMOUNT": 1003,

    # Order errors (2xxx)
    "ORDER_NOT_FOUND": 2001,
    "ORDER_ALREADY_FILLED": 2002,
    "ORDER_ALREADY_CANCELLED": 2003,
    "INVALID_ORDER_TYPE": 2004,
    "PRICE_OUT_OF_RANGE": 2005,
    "QUANTITY_TOO_SMALL": 2006,
    "SELF_TRADE_PREVENTED": 2007,

    # Engine errors (3xxx)
    "ENGINE_NOT_FOUND": 3001,
    "SYMBOL_NOT_ACTIVE": 3002,
    "POOL_EMPTY": 3003,
    "SLIPPAGE_EXCEEDED": 3004,

    # Position errors (4xxx)
    "POSITION_NOT_FOUND": 4001,
    "INSUFFICIENT_MARGIN": 4002,
    "MAX_LEVERAGE_EXCEEDED": 4003,
    "LIQUIDATION_IN_PROGRESS": 4004,

    # System errors (5xxx)
    "DATABASE_ERROR": 5001,
    "RATE_LIMIT_EXCEEDED": 5002,
    "SERVICE_UNAVAILABLE": 5003,
}
```

---

## 9. Security Considerations

### SQL Injection Prevention
- **Always** use parameterized queries with asyncpg (`$1`, `$2`, ...)
- **Never** use f-strings or `.format()` for SQL
- Validate enum values before using in queries

### Input Validation
```python
# Validate at API boundary
class PlaceOrderRequest(BaseModel):
    symbol: str = Field(..., pattern=r"^[A-Z]+-[A-Z]+-[A-Z]+-[A-Z]+$")
    side: int = Field(..., ge=0, le=1)
    order_type: int = Field(..., ge=0, le=1)
    price: Decimal = Field(None, gt=0, max_digits=20, decimal_places=8)
    quantity: Decimal = Field(..., gt=0, max_digits=20, decimal_places=8)
```

### Balance Overflow Protection
```sql
-- Database constraint: prevent negative balances
CHECK (available >= 0)
CHECK (locked >= 0)
CHECK (total >= 0)
```

---

## 10. Performance Benchmarks (Reference)

### Target Latencies for Simulation
| Operation | Target | Notes |
|-----------|--------|-------|
| Place order (CLOB) | < 50ms | Including match + settle |
| Swap (AMM) | < 30ms | Single pool operation |
| Get order book | < 20ms | Top 20 levels |
| Get balances | < 10ms | Single user |
| Market data | < 30ms | Aggregated stats |

### Database Query Optimization
- Use `EXPLAIN ANALYZE` to verify query plans
- Ensure index-only scans for hot queries
- Avoid N+1 queries: batch fetch related data
- Use connection pool efficiently: don't hold connections during computation
