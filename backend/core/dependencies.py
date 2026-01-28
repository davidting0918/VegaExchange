"""
Shared FastAPI dependencies for VegaExchange
"""

from backend.core.db_manager import get_db
from backend.engines.engine_router import EngineRouter


def get_router() -> EngineRouter:
    """Dependency to get engine router"""
    return EngineRouter(get_db())
