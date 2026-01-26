-- VegaExchange Database Schema
-- Version: 2.0
-- Description: Trading simulation laboratory with multi-engine support
-- Performance optimized: Using SMALLINT instead of ENUM for faster comparisons

-- =====================================================
-- CONSTANTS REFERENCE (for documentation)
-- =====================================================
-- engine_type:   0 = AMM, 1 = CLOB
-- symbol_status: 0 = active, 1 = paused, 2 = maintenance
-- order_side:    0 = buy, 1 = sell
-- order_type:    0 = market, 1 = limit
-- order_status:  0 = open, 1 = partial, 2 = filled, 3 = cancelled
-- trade_status:  0 = pending, 1 = completed, 2 = failed

-- =====================================================
-- USERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    avatar_url TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_users_google_id ON users(google_id);
CREATE INDEX idx_users_email ON users(email);

-- =====================================================
-- USER BALANCES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS user_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset VARCHAR(20) NOT NULL,
    available DECIMAL(36, 18) NOT NULL DEFAULT 0,
    locked DECIMAL(36, 18) NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_user_asset UNIQUE (user_id, asset),
    CONSTRAINT positive_available CHECK (available >= 0),
    CONSTRAINT positive_locked CHECK (locked >= 0)
);

CREATE INDEX idx_user_balances_user_id ON user_balances(user_id);
CREATE INDEX idx_user_balances_asset ON user_balances(asset);

-- =====================================================
-- SYMBOL CONFIGURATIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS symbol_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) UNIQUE NOT NULL,
    base_asset VARCHAR(20) NOT NULL,
    quote_asset VARCHAR(20) NOT NULL,
    engine_type SMALLINT NOT NULL CHECK (engine_type IN (0, 1)),  -- 0=AMM, 1=CLOB
    status SMALLINT NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2)),  -- 0=active, 1=paused, 2=maintenance
    
    engine_params JSONB NOT NULL DEFAULT '{}',
    
    min_trade_amount DECIMAL(36, 18) DEFAULT 0.0001,
    max_trade_amount DECIMAL(36, 18) DEFAULT 1000000,
    price_precision INT DEFAULT 8,
    quantity_precision INT DEFAULT 8,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_base_quote UNIQUE (base_asset, quote_asset)
);

CREATE INDEX idx_symbol_configs_symbol ON symbol_configs(symbol);
CREATE INDEX idx_symbol_configs_engine_type ON symbol_configs(engine_type);
CREATE INDEX idx_symbol_configs_status ON symbol_configs(status);

-- =====================================================
-- AMM POOLS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS amm_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_config_id UUID UNIQUE NOT NULL REFERENCES symbol_configs(id) ON DELETE CASCADE,
    
    reserve_base DECIMAL(36, 18) NOT NULL DEFAULT 0,
    reserve_quote DECIMAL(36, 18) NOT NULL DEFAULT 0,
    k_value DECIMAL(72, 18) NOT NULL DEFAULT 0,
    fee_rate DECIMAL(10, 8) NOT NULL DEFAULT 0.003,
    total_lp_shares DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    total_volume_base DECIMAL(36, 18) NOT NULL DEFAULT 0,
    total_volume_quote DECIMAL(36, 18) NOT NULL DEFAULT 0,
    total_fees_collected DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT positive_reserves CHECK (reserve_base >= 0 AND reserve_quote >= 0)
);

CREATE INDEX idx_amm_pools_symbol_config_id ON amm_pools(symbol_config_id);

-- =====================================================
-- ORDERBOOK ORDERS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS orderbook_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_config_id UUID NOT NULL REFERENCES symbol_configs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
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

CREATE INDEX idx_orderbook_orders_symbol ON orderbook_orders(symbol_config_id);
CREATE INDEX idx_orderbook_orders_user ON orderbook_orders(user_id);
CREATE INDEX idx_orderbook_orders_status ON orderbook_orders(status);
CREATE INDEX idx_orderbook_orders_side_price ON orderbook_orders(symbol_config_id, side, price, created_at)
    WHERE status IN (0, 1);  -- open or partial

-- =====================================================
-- TRADES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_config_id UUID NOT NULL REFERENCES symbol_configs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    side SMALLINT NOT NULL CHECK (side IN (0, 1)),  -- 0=buy, 1=sell
    engine_type SMALLINT NOT NULL CHECK (engine_type IN (0, 1)),  -- 0=AMM, 1=CLOB
    
    price DECIMAL(36, 18) NOT NULL,
    quantity DECIMAL(36, 18) NOT NULL,
    quote_amount DECIMAL(36, 18) NOT NULL,
    
    fee_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    fee_asset VARCHAR(20) NOT NULL,
    
    status SMALLINT NOT NULL DEFAULT 1 CHECK (status IN (0, 1, 2)),  -- 0=pending, 1=completed, 2=failed
    
    engine_data JSONB DEFAULT '{}',
    counterparty_user_id UUID REFERENCES users(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trades_symbol ON trades(symbol_config_id);
CREATE INDEX idx_trades_user ON trades(user_id);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX idx_trades_engine_type ON trades(engine_type);

-- =====================================================
-- LP POSITIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS lp_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES amm_pools(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    lp_shares DECIMAL(36, 18) NOT NULL DEFAULT 0,
    initial_base_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    initial_quote_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_pool_user UNIQUE (pool_id, user_id),
    CONSTRAINT positive_shares CHECK (lp_shares >= 0)
);

CREATE INDEX idx_lp_positions_pool ON lp_positions(pool_id);
CREATE INDEX idx_lp_positions_user ON lp_positions(user_id);

-- =====================================================
-- HELPER FUNCTIONS
-- =====================================================

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
-- VIEWS
-- =====================================================

CREATE OR REPLACE VIEW amm_prices AS
SELECT 
    sc.symbol,
    sc.base_asset,
    sc.quote_asset,
    ap.reserve_base,
    ap.reserve_quote,
    CASE 
        WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base
        ELSE 0
    END as current_price,
    ap.fee_rate,
    ap.total_volume_quote as total_volume
FROM symbol_configs sc
JOIN amm_pools ap ON sc.id = ap.symbol_config_id
WHERE sc.engine_type = 0  -- AMM
AND sc.status = 0;  -- active

CREATE OR REPLACE VIEW orderbook_summary AS
SELECT 
    sc.symbol,
    oo.side,
    oo.price,
    SUM(oo.remaining_quantity) as total_quantity,
    COUNT(*) as order_count
FROM symbol_configs sc
JOIN orderbook_orders oo ON sc.id = oo.symbol_config_id
WHERE oo.status IN (0, 1)  -- open or partial
AND sc.status = 0  -- active
GROUP BY sc.symbol, oo.side, oo.price
ORDER BY sc.symbol, oo.side, 
    CASE WHEN oo.side = 0 THEN oo.price END DESC,  -- buy orders desc
    CASE WHEN oo.side = 1 THEN oo.price END ASC;   -- sell orders asc
