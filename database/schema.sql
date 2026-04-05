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
CREATE INDEX idx_users_source ON users(source) WHERE source IS NOT NULL;

-- =====================================================
-- ACCESS TOKENS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS access_tokens (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    access_token TEXT NOT NULL UNIQUE,
    refresh_token TEXT UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
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
CREATE INDEX idx_access_tokens_is_active ON access_tokens(is_active);

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
-- Same symbol can exist with different engine_types for arbitrage opportunities
-- e.g., VEGA/USDT-USDT:SPOT can be traded on both AMM and CLOB
CREATE TABLE IF NOT EXISTS symbol_configs (
    symbol_id SERIAL PRIMARY KEY,
    symbol VARCHAR(40) NOT NULL,  -- Format: {BASE}/{QUOTE}-{SETTLE}:{MARKET} e.g., VEGA/USDT-USDT:SPOT
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
    
    -- Same symbol can have different engine types (for arbitrage)
    -- But same symbol + engine_type combination must be unique
    CONSTRAINT unique_symbol_engine UNIQUE (symbol, engine_type),
    CONSTRAINT unique_symbol_config UNIQUE (market, base, quote, settle, engine_type, settled_at)
);

CREATE INDEX idx_symbol_configs_symbol ON symbol_configs(symbol);
CREATE INDEX idx_symbol_configs_engine_type ON symbol_configs(engine_type);
CREATE INDEX idx_symbol_configs_symbol_engine ON symbol_configs(symbol, engine_type);

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
-- PROTOCOL FEES TABLE (Fee audit trail)
-- =====================================================
CREATE TABLE IF NOT EXISTS protocol_fees (
    id SERIAL PRIMARY KEY,
    symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
    fee_amount DECIMAL(36, 18) NOT NULL,
    fee_asset VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,  -- e.g., 'clob_trade', 'amm_swap'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_protocol_fees_symbol_id ON protocol_fees(symbol_id);
CREATE INDEX idx_protocol_fees_created_at ON protocol_fees(created_at DESC);

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
-- LP EVENTS TABLE (Liquidity Event Log)
-- =====================================================
CREATE TABLE IF NOT EXISTS lp_events (
    id SERIAL PRIMARY KEY,
    pool_id TEXT NOT NULL REFERENCES amm_pools(pool_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    
    event_type TEXT NOT NULL CHECK (event_type IN ('add', 'remove')),
    lp_shares DECIMAL(36, 18) NOT NULL,
    base_amount DECIMAL(36, 18) NOT NULL,
    quote_amount DECIMAL(36, 18) NOT NULL,
    
    -- Snapshot of pool state at time of event (for P&L calculation)
    pool_reserve_base DECIMAL(36, 18) NOT NULL,
    pool_reserve_quote DECIMAL(36, 18) NOT NULL,
    pool_total_lp_shares DECIMAL(36, 18) NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_lp_events_pool_id ON lp_events(pool_id);
CREATE INDEX idx_lp_events_user_id ON lp_events(user_id);
CREATE INDEX idx_lp_events_created_at ON lp_events(created_at DESC);
CREATE INDEX idx_lp_events_pool_user ON lp_events(pool_id, user_id);

-- =====================================================
-- ADMIN WHITELIST TABLE
-- =====================================================
-- Gate check: only emails in this table can log in to the admin dashboard.
-- Managed manually via SQL INSERT for bootstrap, then via admin UI.
CREATE TABLE IF NOT EXISTS admin_whitelist (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,                -- optional note (e.g., "David - project owner")
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_admin_whitelist_email ON admin_whitelist(email);

-- =====================================================
-- ADMINS TABLE
-- =====================================================
-- Independent admin user accounts. No relation to the users table.
-- Created automatically on first admin login if email is in admin_whitelist.
CREATE TABLE IF NOT EXISTS admins (
    admin_id TEXT PRIMARY KEY NOT NULL,           -- 6-char random alphanumeric (a-z0-9)
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    photo_url TEXT,
    role VARCHAR(50) NOT NULL DEFAULT 'admin',   -- future: 'super_admin', 'viewer'
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_admins_google_id ON admins(google_id);
CREATE INDEX idx_admins_email ON admins(email);

-- =====================================================
-- ADMIN ACCESS TOKENS TABLE
-- =====================================================
-- JWT token storage for admin sessions. Mirrors access_tokens structure
-- but references admins(id) instead of users(user_id).
CREATE TABLE IF NOT EXISTS admin_access_tokens (
    id SERIAL PRIMARY KEY,
    admin_id TEXT NOT NULL REFERENCES admins(admin_id) ON DELETE CASCADE,
    access_token TEXT NOT NULL UNIQUE,
    refresh_token TEXT UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expired_at TIMESTAMP WITH TIME ZONE NOT NULL,
    refresh_expired_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT admin_token_positive_expiry CHECK (expired_at > created_at)
);

CREATE INDEX idx_admin_tokens_admin_id ON admin_access_tokens(admin_id);
CREATE INDEX idx_admin_tokens_access_token ON admin_access_tokens(access_token);
CREATE INDEX idx_admin_tokens_refresh_token ON admin_access_tokens(refresh_token) WHERE refresh_token IS NOT NULL;
CREATE INDEX idx_admin_tokens_expired_at ON admin_access_tokens(expired_at);

-- =====================================================
-- PLATFORM SETTINGS TABLE
-- =====================================================
-- Key-value store for platform-wide configuration.
CREATE TABLE IF NOT EXISTS platform_settings (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Seed default init_funding setting
INSERT INTO platform_settings (key, value, description) VALUES
('init_funding', '{"USDT": 1000000, "ORDER": 1000, "AMM": 1000, "VEGA": 10000}',
 'Default balances for new user registration')
ON CONFLICT (key) DO NOTHING;

-- =====================================================
-- ADMIN AUDIT LOGS TABLE
-- =====================================================
-- Append-only log of every admin action.
-- WHO (admin_id) did WHAT (action) to WHICH (target_type + target_id), WHEN (created_at).
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id SERIAL PRIMARY KEY,
    admin_id TEXT NOT NULL REFERENCES admins(admin_id),  -- WHO
    action VARCHAR(100) NOT NULL,                     -- WHAT
    target_type VARCHAR(50),                          -- WHICH type: 'symbol', 'pool', 'user', 'setting'
    target_id TEXT,                                   -- WHICH id: the specific resource ID
    details JSONB,                                    -- CONTEXT: {"old": ..., "new": ...}
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() -- WHEN (append-only, no updated_at)
);

CREATE INDEX idx_audit_logs_admin_id ON admin_audit_logs(admin_id);
CREATE INDEX idx_audit_logs_created_at ON admin_audit_logs(created_at);
CREATE INDEX idx_audit_logs_action ON admin_audit_logs(action);

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
--   - lp_events.id: SERIAL (auto-increment)

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

CREATE TRIGGER update_admins_updated_at
    BEFORE UPDATE ON admins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_admin_access_tokens_updated_at
    BEFORE UPDATE ON admin_access_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_platform_settings_updated_at
    BEFORE UPDATE ON platform_settings
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
