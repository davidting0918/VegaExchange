"""
Initialize a database from database/schema.sql.

This script is the single entry point for building a VegaExchange database
from scratch. It reads the canonical schema definition from
`database/schema.sql` and applies it to the target environment selected via
the `--env` flag (the connection string is pulled from `backend/.env`).

Future phase: this script will also seed initial data from
`database/test_datas.json` and run integration smoke tests. For now it only
applies the schema.

Usage:
    # Apply schema to the default test database (POSTGRES_TEST in .env)
    python -m backend.scripts.init_db

    # Apply schema to a specific environment
    python -m backend.scripts.init_db --env test
    python -m backend.scripts.init_db --env staging
    python -m backend.scripts.init_db --env prod

    # Drop the public schema first, then apply (CAUTION: destroys data)
    python -m backend.scripts.init_db --reset
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

load_dotenv("backend/.env")

ENV_TO_KEY = {
    "test": "POSTGRES_TEST",
    "staging": "POSTGRES_STAGING",
    "prod": "POSTGRES_PROD",
}

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize a VegaExchange database from database/schema.sql",
    )
    parser.add_argument(
        "--env",
        choices=list(ENV_TO_KEY.keys()),
        default="test",
        help="Target environment (selects connection string from backend/.env)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the public schema before applying (destroys all existing data)",
    )
    return parser.parse_args()


async def apply_schema(conn: asyncpg.Connection, *, reset: bool) -> None:
    if reset:
        print("Dropping public schema (--reset)...")
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
        await conn.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
    else:
        # schema.sql is not idempotent (CREATE INDEX has no IF NOT EXISTS),
        # so refuse to apply it on a database that already has tables.
        existing = await conn.fetchval(
            """
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        )
        if existing and existing > 0:
            print(
                f"ERROR: Target database already contains {existing} table(s).\n"
                "Use --reset to drop the public schema and reinitialize from scratch."
            )
            sys.exit(1)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Schema file not found: {SCHEMA_PATH}")

    print(f"Reading {SCHEMA_PATH.relative_to(SCHEMA_PATH.parents[1])}...")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    await conn.execute(sql)
    print("Schema applied")


async def report_state(conn: asyncpg.Connection) -> None:
    tables = await conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    print(f"\nTables ({len(tables)}):")
    for t in tables:
        print(f"  - {t['table_name']}")

    views = await conn.fetch(
        """
        SELECT table_name FROM information_schema.views
        WHERE table_schema = 'public'
        ORDER BY table_name
        """
    )
    print(f"\nViews ({len(views)}):")
    for v in views:
        print(f"  - {v['table_name']}")


async def main() -> None:
    args = parse_args()
    env_key = ENV_TO_KEY[args.env]
    conn_string = os.getenv(env_key)
    if not conn_string:
        print(f"ERROR: {env_key} not set in backend/.env")
        sys.exit(1)

    print(f"Target: {args.env} ({env_key})")
    conn = await asyncpg.connect(conn_string)
    try:
        await apply_schema(conn, reset=args.reset)
        await report_state(conn)
    finally:
        await conn.close()

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
