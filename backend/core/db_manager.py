"""
Database Connection Manager
"""

from typing import Optional

from backend.core.postgres_database import PostgresAsyncClient


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _db_client: Optional[PostgresAsyncClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self, environment: Optional[str] = None):
        if self._db_client is None:
            self._db_client = PostgresAsyncClient(environment)
            await self._db_client.init_pool()

    def get_client(self) -> PostgresAsyncClient:
        if self._db_client is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._db_client

    async def close(self):
        if self._db_client:
            await self._db_client.close()
            self._db_client = None


db_manager = DatabaseManager()


def get_db() -> PostgresAsyncClient:
    return db_manager.get_client()


async def init_database(environment: Optional[str] = None):
    await db_manager.initialize(environment)


async def close_database():
    await db_manager.close()
