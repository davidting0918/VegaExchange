"""Apply database/schema.sql to the staging database via asyncpg."""

import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv("backend/.env")

CONN_STRING = os.getenv("POSTGRES_STAGING")


async def main():
    if not CONN_STRING:
        print("ERROR: POSTGRES_STAGING not set in backend/.env")
        sys.exit(1)

    conn = await asyncpg.connect(CONN_STRING)
    print(f"Connected to staging database")

    # 1. Helper function (triggers depend on it)
    await conn.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    print("1/10 update_updated_at_column() function created")

    # 2. Users
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY NOT NULL UNIQUE,
            user_name VARCHAR(255) NOT NULL,
            google_id VARCHAR(255) UNIQUE,
            email VARCHAR(255) UNIQUE NOT NULL,
            photo_url TEXT,
            hashed_pw TEXT,
            source VARCHAR(50),
            is_active BOOLEAN DEFAULT TRUE,
            is_admin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            last_login_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            CONSTRAINT auth_method_check CHECK (
                (google_id IS NOT NULL) OR (hashed_pw IS NOT NULL)
            )
        )
    """)
    await conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id) WHERE google_id IS NOT NULL")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_source ON users(source) WHERE source IS NOT NULL")
    await conn.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users")
    await conn.execute("CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("2/10 users table created")

    # 3. API keys
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            api_key_id SERIAL PRIMARY KEY,
            api_key TEXT NOT NULL UNIQUE,
            api_secret TEXT,
            name VARCHAR(255) NOT NULL,
            source VARCHAR(50) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            rate_limit INTEGER DEFAULT 60,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_by TEXT REFERENCES users(user_id) ON DELETE SET NULL,
            CONSTRAINT positive_rate_limit CHECK (rate_limit > 0)
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_api_key ON api_keys(api_key)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_source ON api_keys(source)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active)")
    await conn.execute("DROP TRIGGER IF EXISTS update_api_keys_updated_at ON api_keys")
    await conn.execute("CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("3/10 api_keys table created")

    # 4. Access tokens
    await conn.execute("""
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
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_access_tokens_user_id ON access_tokens(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_access_tokens_access_token ON access_tokens(access_token)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_access_tokens_refresh_token ON access_tokens(refresh_token) WHERE refresh_token IS NOT NULL")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_access_tokens_expired_at ON access_tokens(expired_at)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_access_tokens_is_active ON access_tokens(is_active)")
    await conn.execute("DROP TRIGGER IF EXISTS update_access_tokens_updated_at ON access_tokens")
    await conn.execute("CREATE TRIGGER update_access_tokens_updated_at BEFORE UPDATE ON access_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("4/10 access_tokens table created")

    # 5. User balances
    await conn.execute("""
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
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_balances_user_id ON user_balances(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_balances_currency ON user_balances(currency)")
    await conn.execute("DROP TRIGGER IF EXISTS update_user_balances_updated_at ON user_balances")
    await conn.execute("CREATE TRIGGER update_user_balances_updated_at BEFORE UPDATE ON user_balances FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("5/10 user_balances table created")

    # 6. Symbol configs
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS symbol_configs (
            symbol_id SERIAL PRIMARY KEY,
            symbol VARCHAR(40) NOT NULL,
            market VARCHAR(20) NOT NULL,
            base VARCHAR(20) NOT NULL,
            quote VARCHAR(20) NOT NULL,
            settle VARCHAR(20) NOT NULL,
            engine_type SMALLINT NOT NULL CHECK (engine_type IN (0, 1)),
            engine_params JSONB NOT NULL DEFAULT '{}',
            min_trade_amount DECIMAL(36, 18) DEFAULT 0.0001,
            max_trade_amount DECIMAL(36, 18) DEFAULT 1000000,
            price_precision INT DEFAULT 8,
            quantity_precision INT DEFAULT 8,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            settled_at TIMESTAMP WITH TIME ZONE DEFAULT NULL,
            CONSTRAINT unique_symbol_engine UNIQUE (symbol, engine_type),
            CONSTRAINT unique_symbol_config UNIQUE (market, base, quote, settle, engine_type, settled_at)
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_configs_symbol ON symbol_configs(symbol)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_configs_engine_type ON symbol_configs(engine_type)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_configs_symbol_engine ON symbol_configs(symbol, engine_type)")
    await conn.execute("DROP TRIGGER IF EXISTS update_symbol_configs_updated_at ON symbol_configs")
    await conn.execute("CREATE TRIGGER update_symbol_configs_updated_at BEFORE UPDATE ON symbol_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("6/10 symbol_configs table created")

    # 7. AMM pools
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS amm_pools (
            pool_id TEXT PRIMARY KEY UNIQUE NOT NULL,
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
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_amm_pools_symbol_id ON amm_pools(symbol_id)")
    await conn.execute("DROP TRIGGER IF EXISTS update_amm_pools_updated_at ON amm_pools")
    await conn.execute("CREATE TRIGGER update_amm_pools_updated_at BEFORE UPDATE ON amm_pools FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("7/10 amm_pools table created")

    # 8. Orderbook orders
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS orderbook_orders (
            order_id TEXT PRIMARY KEY NOT NULL,
            symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            side SMALLINT NOT NULL CHECK (side IN (0, 1)),
            order_type SMALLINT NOT NULL CHECK (order_type IN (0, 1)),
            price DECIMAL(36, 18),
            quantity DECIMAL(36, 18) NOT NULL,
            filled_quantity DECIMAL(36, 18) NOT NULL DEFAULT 0,
            remaining_quantity DECIMAL(36, 18) NOT NULL,
            status SMALLINT NOT NULL DEFAULT 0 CHECK (status IN (0, 1, 2, 3)),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            filled_at TIMESTAMP WITH TIME ZONE,
            cancelled_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT positive_quantity CHECK (quantity > 0),
            CONSTRAINT positive_remaining CHECK (remaining_quantity >= 0),
            CONSTRAINT valid_filled CHECK (filled_quantity >= 0 AND filled_quantity <= quantity)
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_orders_symbol_id ON orderbook_orders(symbol_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_orders_user_id ON orderbook_orders(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_orderbook_orders_status ON orderbook_orders(status)")
    await conn.execute("DROP INDEX IF EXISTS idx_orderbook_orders_side_price")
    await conn.execute("CREATE INDEX idx_orderbook_orders_side_price ON orderbook_orders(symbol_id, side, price, created_at) WHERE status IN (0, 1)")
    await conn.execute("DROP TRIGGER IF EXISTS update_orderbook_orders_updated_at ON orderbook_orders")
    await conn.execute("CREATE TRIGGER update_orderbook_orders_updated_at BEFORE UPDATE ON orderbook_orders FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")
    print("8/10 orderbook_orders table created")

    # 9. Trades + protocol_fees
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id TEXT PRIMARY KEY NOT NULL,
            symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            side SMALLINT NOT NULL CHECK (side IN (0, 1)),
            engine_type SMALLINT NOT NULL CHECK (engine_type IN (0, 1)),
            price DECIMAL(36, 18) NOT NULL,
            quantity DECIMAL(36, 18) NOT NULL,
            quote_amount DECIMAL(36, 18) NOT NULL,
            fee_amount DECIMAL(36, 18) NOT NULL DEFAULT 0,
            fee_asset VARCHAR(20) NOT NULL,
            status SMALLINT NOT NULL DEFAULT 1 CHECK (status IN (0, 1, 2)),
            engine_data JSONB DEFAULT '{}',
            counterparty TEXT DEFAULT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_id ON trades(symbol_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_engine_type ON trades(engine_type)")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS protocol_fees (
            id SERIAL PRIMARY KEY,
            symbol_id INTEGER NOT NULL REFERENCES symbol_configs(symbol_id) ON DELETE CASCADE,
            fee_amount DECIMAL(36, 18) NOT NULL,
            fee_asset VARCHAR(20) NOT NULL,
            source VARCHAR(50) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_protocol_fees_symbol_id ON protocol_fees(symbol_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_protocol_fees_created_at ON protocol_fees(created_at DESC)")
    print("9/10 trades + protocol_fees tables created")

    # 10. LP positions + LP events
    await conn.execute("""
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
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_positions_pool_id ON lp_positions(pool_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_positions_user_id ON lp_positions(user_id)")
    await conn.execute("DROP TRIGGER IF EXISTS update_lp_positions_updated_at ON lp_positions")
    await conn.execute("CREATE TRIGGER update_lp_positions_updated_at BEFORE UPDATE ON lp_positions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()")

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS lp_events (
            id SERIAL PRIMARY KEY,
            pool_id TEXT NOT NULL REFERENCES amm_pools(pool_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            event_type TEXT NOT NULL CHECK (event_type IN ('add', 'remove')),
            lp_shares DECIMAL(36, 18) NOT NULL,
            base_amount DECIMAL(36, 18) NOT NULL,
            quote_amount DECIMAL(36, 18) NOT NULL,
            pool_reserve_base DECIMAL(36, 18) NOT NULL,
            pool_reserve_quote DECIMAL(36, 18) NOT NULL,
            pool_total_lp_shares DECIMAL(36, 18) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_events_pool_id ON lp_events(pool_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_events_user_id ON lp_events(user_id)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_events_created_at ON lp_events(created_at DESC)")
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_events_pool_user ON lp_events(pool_id, user_id)")
    print("10/10 lp_positions + lp_events tables created")

    # 11. Views
    await conn.execute("""
        CREATE OR REPLACE VIEW amm_prices AS
        SELECT
            sc.symbol, sc.base, sc.quote, ap.pool_id,
            ap.reserve_base, ap.reserve_quote,
            CASE WHEN ap.reserve_base > 0 THEN ap.reserve_quote / ap.reserve_base ELSE 0 END as current_price,
            ap.fee_rate, ap.total_volume_quote as total_volume
        FROM symbol_configs sc
        JOIN amm_pools ap USING (symbol_id)
        WHERE sc.engine_type = 0 AND sc.is_active = TRUE
    """)
    await conn.execute("""
        CREATE OR REPLACE VIEW orderbook_summary AS
        SELECT
            sc.symbol, oo.side, oo.price,
            SUM(oo.remaining_quantity) as total_quantity,
            COUNT(*) as order_count
        FROM symbol_configs sc
        JOIN orderbook_orders oo USING (symbol_id)
        WHERE oo.status IN (0, 1) AND sc.is_active = TRUE
        GROUP BY sc.symbol, oo.side, oo.price
        ORDER BY sc.symbol, oo.side,
            CASE WHEN oo.side = 0 THEN oo.price END DESC,
            CASE WHEN oo.side = 1 THEN oo.price END ASC
    """)
    print("Views created")

    # Verify
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    print(f"\nAll tables ({len(tables)}):")
    for t in tables:
        print(f"  - {t['table_name']}")

    await conn.close()
    print("\nDone! Schema applied successfully.")


if __name__ == "__main__":
    asyncio.run(main())
