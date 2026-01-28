-- VegaExchange Database Schema
-- Version: 3.0
-- Description: Trading simulation laboratory with unified column naming for easy JOINs
-- ID Strategy:
--   - user_id: 6-digit random integer (TEXT)
--   - user_balances: SERIAL (unique by account_type, user_id, currency)
--   - symbol_configs: SERIAL (unique by symbol)
--   - amm_pools: pool_id with 0x prefix (crypto-style address)
--   - orderbook_orders: order_id with 13-digit timestamp
--   - trades: trade_id with 13-digit timestamp
--   - lp_positions: SERIAL

-- =====================================================
-- CONSTANTS REFERENCE (for documentation)
-- =====================================================
-- engine_type:   0 = AMM, 1 = CLOB
-- order_side:    0 = buy, 1 = sell
-- order_type:    0 = market, 1 = limit
-- order_status:  0 = open, 1 = partial, 2 = filled, 3 = cancelled
-- trade_status:  0 = pending, 1 = completed, 2 = failed

-- =====================================================
-- USERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY NOT NULL UNIQUE,  -- 6-digit random integer
    user_name VARCHAR(255) NOT NULL,
    google_id VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE NOT NULL,
    photo_url TEXT,
    hashed_pw TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT auth_method_check CHECK (
        (google_id IS NOT NULL) OR (hashed_pw IS NOT NULL)
    )
);

CREATE UNIQUE INDEX idx_users_google_id ON users(google_id) WHERE google_id IS NOT NULL;
CREATE INDEX idx_users_email ON users(email);

-- =====================================================
-- ACCESS TOKENS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS access_tokens (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    access_token TEXT NOT NULL UNIQUE,
    refresh_token TEXT UNIQUE,
    is_revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expired_at TIMESTAMP WITH TIME ZONE NOT NULL,
    refresh_expired_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT positive_expiry CHECK (expired_at > created_at)
);

CREATE INDEX idx_access_tokens_user_id ON access_tokens(user_id);
CREATE INDEX idx_access_tokens_access_token ON access_tokens(access_token);
CREATE INDEX idx_access_tokens_refresh_token ON access_tokens(refresh_token) WHERE refresh_token IS NOT NULL;
CREATE INDEX idx_access_tokens_expired_at ON access_tokens(expired_at);
CREATE INDEX idx_access_tokens_is_revoked ON access_tokens(is_revoked);

CREATE TRIGGER update_access_tokens_updated_at
    BEFORE UPDATE ON access_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- USER BALANCES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_balances (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    account_type VARCHAR(20) NOT NULL,
    currency VARCHAR(20) NOT NULL,
    available DECIMAL(36, 18) NOT NULL DEFAULT 0,
    balance DECIMAL(36, 18) NOT NULL DEFAULT 0,
    locked DECIMAL(36, 18) NOT NULL DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_user_balance UNIQUE (account_type, user_id, currency)
);

CREATE INDEX idx_user_balances_user_id ON user_balances(user_id);
CREATE INDEX idx_user_balances_currency ON user_balances(currency);

-- =====================================================
-- SYMBOL CONFIGURATIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS symbol_configs (
    symbol_id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    market VARCHAR(20) NOT NULL,  -- spot, perp, option, future
    base VARCHAR(20) NOT NULL,
    quote VARCHAR(20) NOT NULL,
    settle VARCHAR(20) NOT NULL,
    engine_type SMALLINT NOT NULL CHECK (engine_type IN (0, 1)),  -- 0=AMM, 1=CLOB
    
    engine_params JSONB NOT NULL DEFAULT '{}',
    
    min_trade_amount DECIMAL(36, 18) DEFAULT 0.0001,
    max_trade_amount DECIMAL(36, 18) DEFAULT 1000000,
    price_precision INT DEFAULT 8,
    quantity_precision INT DEFAULT 8,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    settled_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
    
    CONSTRAINT unique_symbol_config UNIQUE (market, base, quote, settle, settled_at)
);

CREATE INDEX idx_symbol_configs_symbol ON symbol_configs(symbol);
CREATE INDEX idx_symbol_configs_engine_type ON symbol_configs(engine_type);

-- =====================================================
-- AMM POOLS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS amm_pools (
    pool_id TEXT PRIMARY KEY UNIQUE NOT NULL,  -- 0x + 40 hex chars (crypto-style address)
    symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
    
    reserve_base DECIMAL(36, 18) NOT NULL DEFAULT 0,
    reserve_quote DECIMAL(36, 18) NOT NULL DEFAULT 0,
    k_value DECIMAL(72, 18) NOT NULL DEFAULT 0,
    fee_rate DECIMAL(10, 8) NOT NULL DEFAULT 0.003,
    total_lp_shares DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    total_volume_base DECIMAL(36, 18) NOT NULL DEFAULT 0,
    total_volume_quote DECIMAL(36, 18) NOT NULL DEFAULT 0,
    total_fees_collected DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT positive_reserves CHECK (reserve_base >= 0 AND reserve_quote >= 0)
);

CREATE INDEX idx_amm_pools_symbol_id ON amm_pools(symbol_id);

-- =====================================================
-- ORDERBOOK ORDERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS orderbook_orders (
    order_id TEXT PRIMARY KEY NOT NULL,  -- 13-digit timestamp (milliseconds)
    symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    side SMALLINT NOT NULL CHECK (side IN (0, 1)),  -- 0=buy, 1=sell
    order_type SMALLINT NOT NULL CHECK (order_type IN (0, 1)),  -- 0=market, 1=limit
    price DECIMAL(36, 18),
    quantity DECIMAL(36, 18) NOT NULL,
    filled_quantity DECIMAL(36, 18) NOT NULL DEFAULT 0,
    remaining_quantity DECIMAL(36, 18) NOT NULL,
    
    status SMALLINT NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2, 3)),  -- 0=open, 1=partial, 2=filled, 3=cancelled
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    filled_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT positive_quantity CHECK (quantity > 0),
    CONSTRAINT positive_remaining CHECK (remaining_quantity >= 0),
    CONSTRAINT valid_filled CHECK (filled_quantity >= 0 AND filled_quantity <= quantity)
);

CREATE INDEX idx_orderbook_orders_symbol_id ON orderbook_orders(symbol_id);
CREATE INDEX idx_orderbook_orders_user_id ON orderbook_orders(user_id);
CREATE INDEX idx_orderbook_orders_status ON orderbook_orders(status);
CREATE INDEX idx_orderbook_orders_side_price ON orderbook_orders(symbol_id, side, price, created_at)
    WHERE status IN (0, 1);  -- open or partial

-- =====================================================
-- TRADES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY NOT NULL,  -- 13-digit timestamp (milliseconds)
    symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    side SMALLINT NOT NULL CHECK (side IN (0, 1)),  -- 0=buy, 1=sell
    engine_type SMALLINT NOT NULL CHECK (engine_type IN (0, 1)),  -- 0=AMM, 1=CLOB
    
    price DECIMAL(36, 18) NOT NULL,
    quantity DECIMAL(36, 18) NOT NULL,
    quote_amount DECIMAL(36, 18) NOT NULL,
    
    fee_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    fee_asset VARCHAR(20) NOT NULL,
    
    status SMALLINT NOT NULL DEFAULT 1 CHECK (status IN (0, 1, 2)),  -- 0=pending, 1=completed, 2=failed
    
    engine_data JSONB DEFAULT '{}',
    counterparty TEXT DEFAULT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trades_symbol_id ON trades(symbol_id);
CREATE INDEX idx_trades_user_id ON trades(user_id);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX idx_trades_engine_type ON trades(engine_type);

-- =====================================================
-- LP POSITIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS lp_positions (
    id SERIAL PRIMARY KEY,
    pool_id TEXT NOT NULL REFERENCES amm_pools(pool_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    lp_shares DECIMAL(36, 18) NOT NULL DEFAULT 0,
    initial_base_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    initial_quote_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_pool_user UNIQUE (pool_id, user_id),
    CONSTRAINT positive_shares CHECK (lp_shares >= 0)
);

CREATE INDEX idx_lp_positions_pool_id ON lp_positions(pool_id);
CREATE INDEX idx_lp_positions_user_id ON lp_positions(user_id);

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

-- Note: ID generation is handled in the backend layer (backend/core/id_generator.py)
-- ID formats:
--   - user_id: 6-digit random integer (TEXT)
--   - pool_id: 0x + 40 hex chars (crypto-style address)
--   - order_id: 13-digit timestamp (milliseconds)
--   - trade_id: 13-digit timestamp (milliseconds)
--   - symbol_id: SERIAL (auto-increment)
--   - lp_positions.id: SERIAL (auto-increment)

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_balances_updated_at
    BEFORE UPDATE ON user_balances
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_symbol_configs_updated_at
    BEFORE UPDATE ON symbol_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_amm_pools_updated_at
    BEFORE UPDATE ON amm_pools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orderbook_orders_updated_at
    BEFORE UPDATE ON orderbook_orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_lp_positions_updated_at
    BEFORE UPDATE ON lp_positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- VIEWS (Updated to use unified column names for easy JOINs)
-- =====================================================

CREATE OR REPLACE VIEW amm_prices AS
SELECT 
    sc.symbol,
    sc.base,
    sc.quote,
    ap.pool_id,
    ap.reserve_base,
    ap.reserve_quote,
    CASE 
        WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base
        ELSE 0
    END as current_price,
    ap.fee_rate,
    ap.total_volume_quote as total_volume
FROM symbol_configs sc
JOIN amm_pools ap USING (symbol_id)
WHERE sc.engine_type = 0  -- AMM
AND sc.is_active = TRUE;  -- active

CREATE OR REPLACE VIEW orderbook_summary AS
SELECT 
    sc.symbol,
    oo.side,
    oo.price,
    SUM(oo.remaining_quantity) as total_quantity,
    COUNT(*) as order_count
FROM symbol_configs sc
JOIN orderbook_orders oo USING (symbol_id)
WHERE oo.status IN (0, 1)  -- open or partial
AND sc.is_active = TRUE  -- active
GROUP BY sc.symbol, oo.side, oo.price
ORDER BY sc.symbol, oo.side, 
    CASE WHEN oo.side = 0 THEN oo.price END DESC,  -- buy orders desc
    CASE WHEN oo.side = 1 THEN oo.price END ASC;   -- sell orders asc
