# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VegaExchange is a trading simulation laboratory where users experiment with different market mechanisms side-by-side. Each trading pair (symbol) can use either an AMM (Automated Market Maker, constant product x*y=k) or CLOB (Central Limit Order Book, price-time priority) engine. Auth is Google OAuth or email/password with JWT tokens.

## Commands

### Backend (Python/FastAPI)
```bash
# Install dependencies (use the venv at project root)
pip install -r backend/requirements.txt

# Run the backend server (from project root)
uvicorn backend.main:app --reload

# Run with environment selection
APP_ENV=staging uvicorn backend.main:app --reload   # staging (default)
APP_ENV=test uvicorn backend.main:app --reload      # test database
```

### Frontend (React/Vite)
```bash
cd frontend
npm install
npm run dev      # Dev server (port 5173, proxies /api to localhost:8000)
npm run build    # TypeScript check + Vite build
npm run lint     # ESLint
npm run preview  # Preview production build
```

### Database (PostgreSQL 15+)
```bash
# Apply schema
psql -d vegaexchange_staging -f database/schema.sql
```

### Scripts (backend/scripts/)
```bash
python -m backend.scripts.generate_api_key     # Generate API keys
python -m backend.scripts.generate_jwt_secret   # Generate JWT secret
python -m backend.scripts.continuous_trader     # Simulated continuous trading
python -m backend.scripts.mean_reversion_trader # Mean reversion bot
python -m backend.scripts.price_lifter_trader   # Price manipulation bot
```

## Architecture

### Backend (`backend/`)

**FastAPI app** at `backend/main.py` with lifespan-managed async PostgreSQL pool.

**Engine system** (`backend/engines/`):
- `base_engine.py` - Abstract base with shared balance validation, trade recording, and balance updates
- `amm_engine.py` - Constant product AMM with liquidity pool management
- `clob_engine.py` - Order book with price-time priority matching
- `engine_router.py` - Central dispatcher that routes trades to the correct engine based on `symbol_configs` table. Caches engine instances keyed by `symbol:engine_type`.

**Model-Router-Service architecture** — each domain has 3 files:

| Layer | Path | Responsibility |
|-------|------|---------------|
| **Models** | `backend/models/<domain>.py` | Pydantic request/response types, domain constants |
| **Routers** | `backend/routers/<domain>.py` | Thin endpoint definitions — auth deps, call service, return `APIResponse` |
| **Services** | `backend/services/<domain>.py` | All business logic, DB operations, external API calls |

Domains: `admin`, `auth`, `market`, `orderbook`, `pool`, `user`. Shared models in `backend/models/common.py` (`APIResponse`, `PaginatedResponse`). Shared enums in `backend/models/enums.py`.

**HTTP method rule**: Only use `GET` and `POST`. No `PUT`, `PATCH`, or `DELETE`. Use action verbs in the path instead:
- Update: `POST /api/admin/symbols/update/{id}` (not `PUT /api/admin/symbols/{id}`)
- Delete: `POST /api/admin/whitelist/remove/{id}` (not `DELETE /api/admin/whitelist/{id}`)

**Core** (`backend/core/`) — cross-domain infrastructure only:
- `postgres_database.py` - `PostgresAsyncClient` with asyncpg connection pool
- `db_manager.py` - Singleton `DatabaseManager`; `get_db()` global accessor
- `environment.py` - Auto-detects environment (test/staging/prod) from `APP_ENV`
- `auth.py` - FastAPI dependencies: `get_current_user`, `get_current_user_id`, `require_admin`
- `jwt.py` - JWT creation/verification (HS256), user + admin tokens (separate secrets)
- `audit_log.py` - `@audit_logged` decorator for admin action tracking
- `api_key.py` / `api_key_manager.py` - API key validation
- `id_generator.py` - ID generation (user_id, admin_id, pool_id, order_id, trade_id)

### Frontend (`frontend/`)

**React 19 + TypeScript + Vite** with Tailwind CSS.

- **State**: Redux Toolkit with 3 slices (`authSlice`, `userSlice`, `tradingSlice`)
- **API layer**: Axios client (`src/api/client.ts`) with Bearer token interceptor and automatic refresh on 401
- **Routing**: React Router v7 with `ProtectedRoute` guard; public routes: `/login`, `/register`; protected: `/dashboard`, `/trade/:marketId`, `/pools/:symbolPath`, `/market/:base/:quote/:settle/:market`
- **Path alias**: `@` maps to `src/` (configured in vite.config.ts)
- **Components**: Organized by feature under `src/components/` (auth, dashboard, trading, pool, market, charts, layout, common)
- **Charts**: TradingView Lightweight Charts + Recharts

### Database

PostgreSQL schema at `database/schema.sql`. Uses integer constants for enums (engine_type: 0=AMM/1=CLOB, order_side: 0=buy/1=sell, etc.). IDs: user_id is 6-digit random text, pool_id has 0x prefix, order/trade IDs use 13-digit timestamps.

Test data seeds in `database/test_datas.json`.

## Environment Setup

Backend `.env` (copy from `backend/.env.example`): PostgreSQL connection strings per environment, Google OAuth credentials, JWT secret/config, CORS origins.

Frontend `.env` (copy from `frontend/.env.example`): `VITE_API_BASE_URL` (default http://localhost:8000), `VITE_GOOGLE_CLIENT_ID`.

The Vite dev server proxies `/api` requests to the backend at `http://localhost:8000`.

## Language Rules

- **Always respond to the user in Traditional Chinese (繁體中文)**
- **All code, commit messages, PR titles/descriptions, branch names, comments in code, and documentation must be in English**

## Development Workflow

**Every code change must follow this git flow:**

1. **Checkout master** — `git checkout master`
2. **Pull latest** — `git pull origin master`
3. **Create a new branch** — `git checkout -b <branch-name>` (use descriptive names like `feature/add-perp-engine`, `fix/amm-slippage-calc`)
4. **Make changes** — implement the feature or fix
5. **Commit** — `git add <files> && git commit -m "descriptive message"`
6. **Push** — `git push -u origin <branch-name>`
7. **Open a PR** — `gh pr create` targeting `master` for user review

**Branch naming conventions:**
- `feature/<description>` — new features
- `fix/<description>` — bug fixes
- `refactor/<description>` — code restructuring
- `infra/<description>` — CI/CD, deployment, tooling
- `docs/<description>` — documentation updates

**Important:** Never commit directly to `master`. All changes go through PRs.

**PR content rules:**
- Do NOT mention Claude, AI, or any AI tool in PR titles, descriptions, or commit messages
- No "Generated with Claude Code" or similar footers

## Database Schema Rules

- **`database/schema.sql` is the single source of truth** for the entire database structure
- A new environment must be able to use `schema.sql` alone to create the complete database from scratch
- Any table, column, index, view, trigger, or constraint change **MUST** be reflected in `schema.sql`
- When modifying the database, always update `schema.sql` first, then apply the migration to the running environment
