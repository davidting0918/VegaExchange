# VegaExchange

A trading simulation laboratory where users can experiment with different market mechanisms side-by-side.

## Features

- **Per-Symbol Engine Assignment**: Each trading pair can use a different matching engine
- **Multiple Engine Types**:
  - **AMM (Automated Market Maker)**: Constant product formula (x*y=k) like Uniswap
  - **CLOB (Central Limit Order Book)**: Traditional exchange with price-time priority
- **Unified Trade API**: Single endpoint that routes to the appropriate engine
- **Simulated Balances**: Safe environment for experimentation
- **Google OAuth Only**: Authentication exclusively via Google
- **Persistent State**: Pool states are saved to database after every trade

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Node.js 18+ (for frontend, coming later)

### Setup

1. **Clone and install dependencies**:
   ```bash
   cd VegaExchange
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp backend/.env.example backend/.env
   # Edit backend/.env with your PostgreSQL connection strings
   ```

3. **Create database and run schema**:
   ```bash
   # Using psql
   createdb vegaexchange_staging
   psql -d vegaexchange_staging -f database/schema.sql
   
   # Or using Docker
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=vegaexchange_staging \
     -p 5432:5432 postgres:15
   ```

4. **Start the server**:
   ```bash
   uvicorn backend.main:app --reload
   ```

6. **Access API docs**: http://localhost:8000/docs

## API Overview

### Symbols
- `GET /api/symbols` - List all trading symbols
- `GET /api/symbols/{symbol}` - Get symbol details
- `POST /api/symbols` - Create a new symbol (admin)

### Trading
- `POST /api/trade` - Execute trade (unified for all engines)
- `POST /api/trade/swap` - AMM swap with slippage protection
- `POST /api/trade/order` - Place CLOB order
- `GET /api/trade/quote` - Get trade quote
- `GET /api/trade/orders` - Get user's orders
- `GET /api/trade/history` - Get trade history

### Market Data
- `GET /api/market/{symbol}` - Get market data
- `GET /api/market/{symbol}/orderbook` - Get order book (CLOB)
- `GET /api/market/{symbol}/pool` - Get pool data (AMM)
- `GET /api/market/{symbol}/trades` - Get recent trades

### Users
- `POST /api/users/register` - Register new user
- `GET /api/users/me/balances` - Get user balances
- `GET /api/users/me/portfolio` - Get portfolio summary

## Test Symbols

You can create these symbols manually in the database:

| Symbol | Engine | Description |
|--------|--------|-------------|
| ORDER-USDT | CLOB | Order book style trading |
| AMM-USDT | AMM | DEX-style swapping |

See `database/test_datas.json` for example configuration.

## Architecture

```
backend/
├── core/
│   ├── db_manager.py      # Database connection management
│   ├── environment.py     # Environment configuration
│   └── postgres_database.py # Async PostgreSQL client
├── engines/
│   ├── base_engine.py     # Abstract base engine
│   ├── amm_engine.py      # AMM implementation
│   ├── clob_engine.py     # CLOB implementation
│   └── engine_router.py   # Routes trades to correct engine
├── models/
│   ├── enums.py           # Enum definitions
│   ├── requests.py        # Request models
│   └── responses.py       # Response models
├── routers/
│   ├── symbols.py         # Symbol management
│   ├── trading.py         # Trade execution
│   ├── market.py          # Market data
│   ├── users.py           # User management
│   └── admin.py           # Admin operations
└── main.py                # FastAPI application
```

## Example Usage

### AMM Swap (Buy AMM tokens with USDT)
```bash
curl -X POST "http://localhost:8000/api/trade/swap?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AMM-USDT",
    "side": "buy",
    "amount_in": 100,
    "min_amount_out": 9
  }'
```

### CLOB Limit Order
```bash
curl -X POST "http://localhost:8000/api/trade/order?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ORDER-USDT",
    "side": "buy",
    "order_type": "limit",
    "quantity": 10,
    "price": 9.5
  }'
```

### Get Quote
```bash
curl "http://localhost:8000/api/trade/quote?symbol=AMM-USDT&side=buy&quote_amount=100"
```

## License

MIT
