-- VegaExchange Database Schema
-- Version: 1.0
-- Description: Trading simulation laboratory with multi-engine support

-- =====================================================
-- ENUM TYPES
-- =====================================================

-- Engine types for symbol configuration
CREATE TYPE engine_type AS ENUM ('amm', 'clob');

-- Symbol status
CREATE TYPE symbol_status AS ENUM ('active', 'paused', 'maintenance');

-- Order side (buy/sell)
CREATE TYPE order_side AS ENUM ('buy', 'sell');

-- Order type
CREATE TYPE order_type AS ENUM ('market', 'limit');

-- Order status
CREATE TYPE order_status AS ENUM ('open', 'partial', 'filled', 'cancelled');

-- Trade status
CREATE TYPE trade_status AS ENUM ('pending', 'completed', 'failed');

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
-- Each user has balances in multiple assets
CREATE TABLE IF NOT EXISTS user_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset VARCHAR(20) NOT NULL,  -- e.g., 'BTC', 'USDT', 'ETH'
    available DECIMAL(36, 18) NOT NULL DEFAULT 0,  -- Available for trading
    locked DECIMAL(36, 18) NOT NULL DEFAULT 0,     -- Locked in open orders
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
-- Defines which engine each trading pair uses
CREATE TABLE IF NOT EXISTS symbol_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) UNIQUE NOT NULL,  -- e.g., 'BTC-USDT', 'ETH-USDT'
    base_asset VARCHAR(20) NOT NULL,     -- e.g., 'BTC'
    quote_asset VARCHAR(20) NOT NULL,    -- e.g., 'USDT'
    engine_type engine_type NOT NULL,
    status symbol_status NOT NULL DEFAULT 'active',
    
    -- Engine-specific parameters stored as JSON
    engine_params JSONB NOT NULL DEFAULT '{}',
    
    -- Common trading parameters
    min_trade_amount DECIMAL(36, 18) DEFAULT 0.0001,
    max_trade_amount DECIMAL(36, 18) DEFAULT 1000000,
    price_precision INT DEFAULT 8,       -- Decimal places for price
    quantity_precision INT DEFAULT 8,    -- Decimal places for quantity
    
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
-- Only exists for symbols with engine_type = 'amm' or 'hybrid'
CREATE TABLE IF NOT EXISTS amm_pools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_config_id UUID UNIQUE NOT NULL REFERENCES symbol_configs(id) ON DELETE CASCADE,
    
    -- Reserve amounts
    reserve_base DECIMAL(36, 18) NOT NULL DEFAULT 0,   -- e.g., BTC amount
    reserve_quote DECIMAL(36, 18) NOT NULL DEFAULT 0,  -- e.g., USDT amount
    
    -- Constant product (k = reserve_base * reserve_quote)
    k_value DECIMAL(72, 18) NOT NULL DEFAULT 0,
    
    -- Fee configuration
    fee_rate DECIMAL(10, 8) NOT NULL DEFAULT 0.003,  -- 0.3% default
    
    -- Liquidity provider tracking
    total_lp_shares DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    -- Statistics
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
-- Only exists for symbols with engine_type = 'clob' or 'hybrid'
CREATE TABLE IF NOT EXISTS orderbook_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_config_id UUID NOT NULL REFERENCES symbol_configs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Order details
    side order_side NOT NULL,
    order_type order_type NOT NULL,
    price DECIMAL(36, 18),           -- NULL for market orders
    quantity DECIMAL(36, 18) NOT NULL,
    filled_quantity DECIMAL(36, 18) NOT NULL DEFAULT 0,
    remaining_quantity DECIMAL(36, 18) NOT NULL,
    
    -- Status
    status order_status NOT NULL DEFAULT 'open',
    
    -- Timestamps
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
    WHERE status IN ('open', 'partial');

-- =====================================================
-- TRADES TABLE
-- =====================================================
-- Unified trade history for all engine types
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol_config_id UUID NOT NULL REFERENCES symbol_configs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Trade details
    side order_side NOT NULL,
    engine_type engine_type NOT NULL,
    
    -- Amounts
    price DECIMAL(36, 18) NOT NULL,
    quantity DECIMAL(36, 18) NOT NULL,
    quote_amount DECIMAL(36, 18) NOT NULL,  -- price * quantity
    
    -- Fees
    fee_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
    fee_asset VARCHAR(20) NOT NULL,
    
    -- Status
    status trade_status NOT NULL DEFAULT 'completed',
    
    -- Engine-specific data (order ID for CLOB, slippage for AMM, etc.)
    engine_data JSONB DEFAULT '{}',
    
    -- For CLOB: counterparty user (if applicable)
    counterparty_user_id UUID REFERENCES users(id),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_trades_symbol ON trades(symbol_config_id);
CREATE INDEX idx_trades_user ON trades(user_id);
CREATE INDEX idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX idx_trades_engine_type ON trades(engine_type);

-- =====================================================
-- LP POSITIONS TABLE (for AMM liquidity providers)
-- =====================================================
CREATE TABLE IF NOT EXISTS lp_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pool_id UUID NOT NULL REFERENCES amm_pools(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    lp_shares DECIMAL(36, 18) NOT NULL DEFAULT 0,
    
    -- Track initial deposits for IL calculation
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

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at trigger to all relevant tables
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

-- View to get current AMM prices
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
WHERE sc.engine_type IN ('amm', 'hybrid')
AND sc.status = 'active';

-- View to get orderbook summary
CREATE OR REPLACE VIEW orderbook_summary AS
SELECT 
    sc.symbol,
    oo.side,
    oo.price,
    SUM(oo.remaining_quantity) as total_quantity,
    COUNT(*) as order_count
FROM symbol_configs sc
JOIN orderbook_orders oo ON sc.id = oo.symbol_config_id
WHERE oo.status IN ('open', 'partial')
AND sc.status = 'active'
GROUP BY sc.symbol, oo.side, oo.price
ORDER BY sc.symbol, oo.side, 
    CASE WHEN oo.side = 'buy' THEN oo.price END DESC,
    CASE WHEN oo.side = 'sell' THEN oo.price END ASC;
