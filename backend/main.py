"""
VegaExchange - Trading Simulation Laboratory

FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from backend.core.db_manager import close_database, init_database
from backend.core.environment import env_config
from backend.core.websocket_manager import init_ws_manager
from backend.routers import (
    admin_router,
    auth_router,
    market_router,
    orderbook_router,
    pool_router,
    users_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"Starting VegaExchange in {env_config.environment.value} mode...")
    await init_database()
    print("Database connection established.")
    init_ws_manager()
    print("WebSocket manager initialized.")

    # Backfill kline gaps from downtime
    try:
        from backend.services.kline import kline_backfill
        await kline_backfill()
    except Exception as e:
        print(f"[WARN] Kline backfill failed: {e}")

    yield

    # Shutdown
    print("Shutting down VegaExchange...")
    await close_database()
    print("Database connection closed.")


# Create FastAPI application
app = FastAPI(
    title="VegaExchange API",
    description="""
    Trading Simulation Laboratory - A platform for experimenting with
    different market mechanisms (AMM, CLOB).

    ## Features
    - Per-symbol engine assignment
    - Unified trade API across all engine types
    - Real-time market data
    - Simulated balances

    ## Engine Types
    - **AMM**: Automated Market Maker with constant product formula
    - **CLOB**: Central Limit Order Book with price-time priority

    ## API Documentation
    - **Scalar**: /scalar (recommended)
    - **Swagger**: /docs
    - **ReDoc**: /redoc
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=env_config.get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(market_router)
app.include_router(pool_router)        # AMM pool operations
app.include_router(orderbook_router)   # CLOB orderbook operations
app.include_router(users_router)


def custom_openapi():
    """
    Customize OpenAPI schema to include security schemes.
    This enables authentication in Swagger UI and Scalar documentation.
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    from fastapi.openapi.utils import get_openapi
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT token authentication. Use 'Bearer <token>' format in Authorization header.",
        },
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "/api/auth/token",
                    "scopes": {},
                }
            },
            "description": "OAuth2 password grant flow. Use this for Swagger UI authentication.",
        },
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Override the default openapi function
app.openapi = custom_openapi


@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    """Scalar API documentation"""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "VegaExchange API",
        "version": "1.0.0",
        "environment": env_config.environment.value,
        "docs": {
            "scalar": "/scalar",
            "swagger": "/docs",
            "redoc": "/redoc",
        },
    }


@app.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(default=None)):
    """
    WebSocket endpoint for real-time market data.

    Connect: ws://localhost:8000/api/ws?token=JWT_TOKEN
    Token is optional for public channels, required for user channels.

    Subscribe:   {"action": "subscribe", "channel": "orderbook:BTC/USDT-USDT:SPOT"}
    Unsubscribe: {"action": "unsubscribe", "channel": "orderbook:BTC/USDT-USDT:SPOT"}

    Channels:
    - orderbook:{symbol}  (public)  - Order book updates
    - trades:{symbol}     (public)  - New trades
    - ticker:{symbol}     (public)  - Price ticker
    - user:{user_id}      (private) - Order fills, balance changes
    """
    await ws.accept()

    # Try to authenticate if token provided
    user_id = None
    if token:
        try:
            from backend.core.jwt import verify_token
            payload = verify_token(token)
            if payload and payload.get("type") == "access":
                user_id = payload.get("sub")
        except Exception:
            pass  # Invalid token — still allow public channels

    from backend.core.websocket_manager import get_ws_manager
    manager = get_ws_manager()
    if not manager:
        await ws.close(code=1011, reason="WebSocket manager not initialized")
        return

    await manager.handle_client(ws, user_id)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from backend.core.db_manager import get_db

    try:
        db = get_db()
        await db.read_one("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "environment": env_config.environment.value,
        "database": db_status,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=env_config.get("debug", False),
    )
