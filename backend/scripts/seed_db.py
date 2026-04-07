"""
Seed a database with fixtures from database/test_datas.json.

This script is the second half of the local dev workflow:

    1. python -m backend.scripts.init_db --env test --reset   # apply schema
    2. python -m backend.scripts.seed_db --env test           # seed fixtures

Strategy:
    - admin_whitelist and platform_settings are inserted directly via the
      database connection. Both are bootstrap state — they have to exist
      before any HTTP endpoint that depends on them can be called
      (admin login needs whitelist; user registration reads init_funding;
      update_setting refuses to create new keys).
    - Everything else is created by calling the real FastAPI endpoints
      in-process via httpx.ASGITransport. This keeps the seed flow on the
      same code path as production.

Admin Google login:
    The script monkey-patches backend.services.auth._verify_google_token
    BEFORE importing the FastAPI app. The patched function treats the
    id_token field as a JSON-encoded payload (not a real Google JWT).
    This is in-process only — the production code path is untouched.

Usage:
    python -m backend.scripts.seed_db                # default: env=test
    python -m backend.scripts.seed_db --env staging
"""

# === Mock Google ID token verification (must run BEFORE app import) ===
# We patch the symbol that admin_google_auth resolves at call time. Because
# admin_google_auth references _verify_google_token via its module globals,
# rebinding the attribute on the auth module is sufficient.
import json as _json

from backend.services import auth as _auth_service


async def _mock_verify_google_token(id_token: str, client_id: str) -> dict:
    """Treat id_token as a JSON-encoded payload (dev / seed only)."""
    try:
        payload = _json.loads(id_token)
    except _json.JSONDecodeError as exc:
        raise ValueError(
            "Mock _verify_google_token expected a JSON-encoded id_token"
        ) from exc
    return {
        "google_id": payload["google_id"],
        "email": payload["email"],
        "name": payload.get("name", payload["email"].split("@")[0]),
        "picture": payload.get("picture"),
    }


_auth_service._verify_google_token = _mock_verify_google_token
# === end monkey patch ===


import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Importing the FastAPI app must happen AFTER the monkey patch above.
from httpx import ASGITransport, AsyncClient, HTTPStatusError

from backend.core.db_manager import get_db, init_database

SEED_PATH = Path(__file__).resolve().parents[2] / "database" / "test_datas.json"


# ----------------------------------------------------------------------
# Logging helpers
# ----------------------------------------------------------------------


class StepRunner:
    """Tiny step tracker. Each step prints PASS / FAIL on a single line."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    async def run(self, name: str, fn) -> Any:
        idx = self.passed + self.failed + 1
        print(f"  [{idx:02d}] {name}...", end=" ", flush=True)
        try:
            result = await fn()
            print("PASS")
            self.passed += 1
            return result
        except HTTPStatusError as exc:
            body = exc.response.text
            print(f"FAIL ({exc.response.status_code}) {body}")
            self.failed += 1
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL ({type(exc).__name__}: {exc})")
            self.failed += 1
            raise


def _phase(title: str) -> None:
    print(f"\n=== {title} ===")


# ----------------------------------------------------------------------
# Pre-flight: refuse if DB already has seed data
# ----------------------------------------------------------------------


async def preflight() -> None:
    db = get_db()
    user_count = await db.read_one("SELECT count(*) AS c FROM users")
    if user_count and user_count["c"] > 0:
        print(
            f"\nERROR: Database already contains {user_count['c']} user(s). "
            "Run `python -m backend.scripts.init_db --env <env> --reset` first."
        )
        sys.exit(1)


# ----------------------------------------------------------------------
# Bootstrap (direct DB writes)
# ----------------------------------------------------------------------


async def bootstrap_admin_whitelist(data: dict, runner: StepRunner) -> None:
    _phase("Bootstrap: admin_whitelist (direct DB)")
    db = get_db()
    for entry in data.get("admin_whitelist", []):
        async def insert(e=entry):
            await db.execute(
                "INSERT INTO admin_whitelist (email, description) VALUES ($1, $2)",
                e["email"],
                e.get("description"),
            )
        await runner.run(f"INSERT admin_whitelist {entry['email']}", insert)


async def bootstrap_platform_settings(data: dict, runner: StepRunner) -> None:
    _phase("Bootstrap: platform_settings (direct DB)")
    db = get_db()
    for setting in data.get("platform_settings", []):
        async def insert(s=setting):
            # JSONB codec auto-encodes the dict — pass as-is
            await db.execute(
                "INSERT INTO platform_settings (key, value, description) VALUES ($1, $2, $3)",
                s["key"],
                s["value"],
                s.get("description"),
            )
        await runner.run(f"INSERT platform_settings {setting['key']}", insert)


# ----------------------------------------------------------------------
# HTTP phases
# ----------------------------------------------------------------------


async def http_admin_login(
    client: AsyncClient, data: dict, runner: StepRunner
) -> dict:
    _phase("Admin login (mock Google)")
    admin_payload = data["admin"]
    fake_id_token = json.dumps(admin_payload)

    async def login() -> dict:
        r = await client.post(
            "/api/auth/admin/google",
            json={"id_token": fake_id_token},
        )
        r.raise_for_status()
        return r.json()["data"]

    result = await runner.run(
        f"POST /api/auth/admin/google ({admin_payload['email']})",
        login,
    )
    print(f"       admin_id={result['admin']['admin_id']}")
    return {"Authorization": f"Bearer {result['access_token']}"}


async def http_register_users(
    client: AsyncClient, data: dict, runner: StepRunner
) -> None:
    _phase("Register users")
    for user in data.get("users", []):
        async def register(u=user):
            r = await client.post(
                "/api/auth/register/email",
                json={
                    "email": u["email"],
                    "password": u["password"],
                    "user_name": u["user_name"],
                },
            )
            r.raise_for_status()
            return r.json()["data"]

        result = await runner.run(
            f"POST /api/auth/register/email ({user['email']})",
            register,
        )
        print(f"       user_id={result['user']['user_id']}")


async def http_create_amm_pools(
    client: AsyncClient,
    data: dict,
    admin_headers: dict,
    runner: StepRunner,
) -> None:
    _phase("Create AMM pools")
    for pool in data.get("amm_pools", []):
        async def create(p=pool):
            r = await client.post(
                "/api/admin/create_pool",
                json=p,
                headers=admin_headers,
            )
            r.raise_for_status()
            return r.json()["data"]

        result = await runner.run(
            f"POST /api/admin/create_pool ({pool['symbol']})",
            create,
        )
        print(f"       pool_id={result['pool_id']}")


async def http_create_clob_symbols(
    client: AsyncClient,
    data: dict,
    admin_headers: dict,
    runner: StepRunner,
) -> None:
    _phase("Create CLOB symbols")
    for sym in data.get("clob_symbols", []):
        async def create(s=sym):
            r = await client.post(
                "/api/admin/create_symbol",
                json=s,
                headers=admin_headers,
            )
            r.raise_for_status()
            return r.json()["data"]

        result = await runner.run(
            f"POST /api/admin/create_symbol ({sym['symbol']})",
            create,
        )
        print(f"       symbol_id={result['symbol_id']}")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a VegaExchange database from database/test_datas.json"
    )
    parser.add_argument(
        "--env",
        choices=["test", "staging", "prod"],
        default="test",
        help="Target environment",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the seed plan without making any changes",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    os.environ["APP_ENV"] = args.env

    if not SEED_PATH.exists():
        print(f"ERROR: Seed file not found: {SEED_PATH}")
        sys.exit(1)

    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))

    print(f"Target: {args.env}")
    print(f"Source: {SEED_PATH.relative_to(SEED_PATH.parents[2])}")

    if args.dry_run:
        print("\n=== DRY RUN — no changes will be made ===")
        print(f"  - admin_whitelist:    {len(data.get('admin_whitelist', []))} row(s)")
        for e in data.get("admin_whitelist", []):
            print(f"      - {e['email']}")
        print(f"  - platform_settings:  {len(data.get('platform_settings', []))} row(s)")
        for s in data.get("platform_settings", []):
            print(f"      - {s['key']} = {s['value']}")
        admin = data.get("admin", {})
        if admin:
            print(f"  - admin login:        {admin.get('email')} (mock Google)")
        print(f"  - users:              {len(data.get('users', []))} row(s)")
        for u in data.get("users", []):
            print(f"      - {u['email']} ({u['user_name']})")
        print(f"  - amm_pools:          {len(data.get('amm_pools', []))} row(s)")
        for p in data.get("amm_pools", []):
            print(
                f"      - {p['symbol']} reserves={p['initial_reserve_base']}/"
                f"{p['initial_reserve_quote']} fee={p['fee_rate']}"
            )
        print(f"  - clob_symbols:       {len(data.get('clob_symbols', []))} row(s)")
        for s in data.get("clob_symbols", []):
            print(f"      - {s['symbol']} init_price={s.get('init_price')}")
        print("\nRun without --dry-run to apply.")
        return

    # Real run
    await init_database()
    await preflight()

    runner = StepRunner()

    # Direct-DB bootstrap
    await bootstrap_admin_whitelist(data, runner)
    await bootstrap_platform_settings(data, runner)

    # Import the FastAPI app and open an in-process client
    from backend.main import app  # noqa: WPS433 — late import is intentional

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://seed") as client:
        admin_headers = await http_admin_login(client, data, runner)
        await http_register_users(client, data, runner)
        await http_create_amm_pools(client, data, admin_headers, runner)
        await http_create_clob_symbols(client, data, admin_headers, runner)

    print(
        f"\n=== Summary: {runner.passed} step(s) passed, "
        f"{runner.failed} step(s) failed ==="
    )
    sys.exit(0 if runner.failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
