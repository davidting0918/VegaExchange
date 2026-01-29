"""
VegaExchange - Trading Simulation Laboratory

FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference

from backend.core.db_manager import close_database, init_database
from backend.core.environment import env_config
from backend.routers import auth_router, market_router, symbols_router, trading_router, users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print(f"Starting VegaExchange in {env_config.environment.value} mode...")
    await init_database()
    print("Database connection established.")

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
app.include_router(symbols_router)
app.include_router(trading_router)
app.include_router(market_router)
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
