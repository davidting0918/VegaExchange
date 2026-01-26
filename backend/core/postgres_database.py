import os
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, Dict, List, Optional

import asyncpg
from asyncpg import Pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv("backend/.env")


class PostgresAsyncClient:
    def __init__(self, environment: Optional[str] = None):
        """
        Initialize PostgreSQL async client with environment support

        Args:
            environment (str): Environment name (test, staging, prod).
                              If None, auto-detect from APP_ENV or PYTEST_RUNNING
        """
        if environment is None:
            if os.getenv("PYTEST_RUNNING") == "1":
                environment = "test"
            else:
                environment = os.getenv("APP_ENV", "prod")

        self.environment = environment

        # Get environment-specific connection string
        if environment == "test":
            self.connection_string = os.getenv("POSTGRES_TEST")
        elif environment == "staging":
            self.connection_string = os.getenv("POSTGRES_STAGING")
        else:  # prod
            self.connection_string = os.getenv("POSTGRES_PROD")

        self._pool: Optional[Pool] = None
        self._initializing = False  # Flag to prevent concurrent initialization

    @classmethod
    def get_instance(cls, environment: Optional[str] = None):
        return cls(environment)

    async def init_pool(self):
        """Initialize connection pool (thread-safe)"""
        if self._pool or self._initializing:
            return

        self._initializing = True
        try:
            if not self._pool:  # Double-check after acquiring lock
                self._pool = await asyncpg.create_pool(
                    self.connection_string,
                    min_size=1,
                    max_size=50,
                    command_timeout=60,
                )
        finally:
            self._initializing = False

    async def close(self):
        """Close the database connection pool"""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def get_connection(self):
        """Get a database connection from the pool (auto-initializes if needed)"""
        # Auto-initialize pool if not already done
        if not self._pool and not self._initializing:
            await self.init_pool()

        # Wait for initialization if it's in progress
        while self._initializing:
            import asyncio

            await asyncio.sleep(0.01)

        if not self._pool:
            raise RuntimeError("Failed to initialize database connection pool")

        async with self._pool.acquire() as connection:
            yield connection

    # ================== Data Conversion Helpers ==================

    def _convert_decimals_to_floats(self, obj: Any) -> Any:
        """
        Recursively convert all Decimal instances to float in nested data structures.

        Args:
            obj: The object to convert (dict, list, tuple, Decimal, or any other type)

        Returns:
            The object with all Decimal values converted to float
        """
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, dict):
            return {key: self._convert_decimals_to_floats(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_decimals_to_floats(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_decimals_to_floats(item) for item in obj)
        else:
            return obj

    # ================== Simple Query Methods ==================

    async def read(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries

        Args:
            query (str): SQL SELECT query with $1, $2, etc. placeholders
            *args: Parameters for the query placeholders

        Returns:
            List[Dict[str, Any]]: Query results as list of dictionaries with Decimal values converted to float
        """
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *args)
                result = [dict(row) for row in rows]
                return self._convert_decimals_to_floats(result)
        except Exception as e:
            raise e

    async def read_one(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return first result as dictionary

        Args:
            query (str): SQL SELECT query with $1, $2, etc. placeholders
            *args: Parameters for the query placeholders

        Returns:
            Optional[Dict[str, Any]]:
                First query result as dictionary with Decimal values converted to float,
                or None if no result
        """
        try:
            async with self.get_connection() as conn:
                row = await conn.fetchrow(query, *args)
                if row:
                    result = dict(row)
                    return self._convert_decimals_to_floats(result)
                return None

        except Exception as e:
            raise e

    async def insert_one(self, table: str, data: Dict[str, Any]) -> Any:
        """
        Insert a single record into a table

        Args:
            table (str): Table name
            data (Dict[str, Any]): Dictionary with column names as keys and values to insert

        Returns:
            Any: The ID of the inserted record (if table has 'id' column), or the full inserted record
        """
        try:
            # Convert timestamp fields automatically

            columns = list(data.keys())
            placeholders = [f"${i}" for i in range(1, len(columns) + 1)]
            values = list(data.values())

            # Try to return 'id' if it exists, otherwise return all columns
            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING *
            """

            async with self.get_connection() as conn:
                result = await conn.fetchrow(query, *values)
                result_dict = dict(result)

                # Convert Decimal values to float
                result_dict = self._convert_decimals_to_floats(result_dict)

                # Return just the id if it exists, otherwise return the full record
                return result_dict.get("id", result_dict)

        except Exception as e:
            raise e

    async def insert(self, table: str, data: List[Dict[str, Any]]) -> List[Any]:
        """
        Insert multiple records into a table

        Args:
            table (str): Table name
            data (List[Dict[str, Any]]): List of dictionaries with column names as keys and values to insert

        Returns:
            List[Any]: List of inserted record IDs (if table has 'id' column), or list of full inserted records
        """
        try:
            if not data:
                return []

            # Convert timestamp fields for all records

            # Use the first record to determine columns
            columns = list(data[0].keys())

            # Build the query with multiple value sets
            placeholders_per_row = len(columns)
            value_sets = []
            all_values = []

            for i, record in enumerate(data):
                # Ensure all records have the same columns
                if set(record.keys()) != set(columns):
                    raise ValueError(
                        f"All records must have the same columns. Expected: {columns}, Got: {list(record.keys())}"
                    )

                # Create placeholders for this row
                row_placeholders = [f"${j + i * placeholders_per_row + 1}" for j in range(placeholders_per_row)]
                value_sets.append(f"({', '.join(row_placeholders)})")

                # Add values in the same order as columns
                for col in columns:
                    all_values.append(record[col])

            query = f"""
                INSERT INTO {table} ({', '.join(columns)})
                VALUES {', '.join(value_sets)}
                RETURNING *
            """

            async with self.get_connection() as conn:
                results = await conn.fetch(query, *all_values)
                result_dicts = [dict(row) for row in results]

                # Convert Decimal values to float
                result_dicts = self._convert_decimals_to_floats(result_dicts)

                # Return just the ids if they exist, otherwise return the full records
                if result_dicts and "id" in result_dicts[0]:
                    return [record["id"] for record in result_dicts]
                else:
                    return result_dicts

        except Exception as e:
            raise e

    async def execute(self, query: str, *args: Any) -> str:
        """
        Execute an INSERT, UPDATE, or DELETE query

        Args:
            query (str): SQL query with $1, $2, etc. placeholders
            *args: Parameters for the query placeholders

        Returns:
            str: Result status from the database (e.g., "INSERT 0 1", "UPDATE 1", "DELETE 1")
        """
        async with self.get_connection() as conn:
            result = await conn.execute(query, *args)
            return result

    async def execute_returning(self, query: str, *args: Any) -> Any:
        """
        Execute an INSERT, UPDATE, or DELETE query with RETURNING clause

        Args:
            query (str): SQL query with RETURNING clause and $1, $2, etc. placeholders
            *args: Parameters for the query placeholders

        Returns:
            Any: The returned value from the RETURNING clause with Decimal values converted to float
        """
        async with self.get_connection() as conn:
            result = await conn.fetchrow(query, *args)
            if result:
                result_dict = dict(result)
                return self._convert_decimals_to_floats(result_dict)
            return None
