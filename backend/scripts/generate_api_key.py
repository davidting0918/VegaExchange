#!/usr/bin/env python3
"""
Generate API key and secret pairs for VegaExchange

This script generates API key/secret pairs for different sources.
The output includes both plain text (for initial use) and hashed values (for database insertion).
SQL INSERT statement is shown by default.

Uses backend.core.api_key_manager for generation and hashing (same as runtime).

Usage (run from project root so backend is on PYTHONPATH):
    python -m backend.scripts.generate_api_key --source frontend
    python -m backend.scripts.generate_api_key --source backend-ui --rate-limit 200
"""

import argparse
import sys

from backend.core.api_key_manager import (
    generate_api_key_pair,
    hash_api_key,
    hash_api_secret,
)


def generate_api_key_for_source(
    source: str,
    rate_limit: int = 60,
) -> dict:
    """
    Generate API key and secret pair for a specific source.

    Args:
        source: Source identifier (also used as name, e.g., "frontend", "backend-ui", "mobile")
        rate_limit: Rate limit per minute (default: 60)

    Returns:
        Dictionary containing plain text and hashed values
    """
    api_key, api_secret = generate_api_key_pair()
    hashed_key = hash_api_key(api_key)
    hashed_secret = hash_api_secret(api_secret)
    name = source

    return {
        "api_key": api_key,
        "api_secret": api_secret,
        "hashed_key": hashed_key,
        "hashed_secret": hashed_secret,
        "name": name,
        "source": source,
        "rate_limit": rate_limit,
    }


def print_output(data: dict):
    """
    Print formatted output with API key information.

    Args:
        data: Dictionary containing API key data
    """
    print("=" * 80)
    print("API Key and Secret Generated")
    print("=" * 80)
    print(f"\nName/Source: {data['name']}")
    print(f"Rate Limit: {data['rate_limit']} requests/minute")
    print("\n" + "-" * 80)
    print("PLAIN TEXT VALUES (Save these securely - shown only once!)")
    print("-" * 80)
    print(f"\nAPI Key:\n{data['api_key']}\n")
    print(f"API Secret:\n{data['api_secret']}\n")
    print("-" * 80)
    print("SQL INSERT Statement (ready to use)")
    print("-" * 80)
    print(f"""
INSERT INTO api_keys (api_key, api_secret, name, source, rate_limit, is_active)
VALUES (
    '{data['hashed_key']}',
    '{data['hashed_secret']}',
    '{data['name']}',
    '{data['source']}',
    {data['rate_limit']},
    TRUE
);
""")

    print("=" * 80)
    print("\n⚠️  IMPORTANT:")
    print("  1. Save the plain text API key and secret securely")
    print("  2. Use the hashed values when inserting into the database")
    print("  3. The plain text values will NOT be shown again")
    print("  4. Database stores HASHED values, not plain text")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Generate API key and secret pairs for VegaExchange",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples (run from project root):
  python -m backend.scripts.generate_api_key --source frontend
  python -m backend.scripts.generate_api_key --source backend-ui --rate-limit 200
  python -m backend.scripts.generate_api_key --source mobile
        """,
    )

    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="Source identifier (also used as name, e.g., 'frontend', 'backend-ui', 'mobile', 'admin')",
    )

    parser.add_argument(
        "--rate-limit",
        type=int,
        default=60,
        help="Rate limit per minute (default: 60)",
    )

    args = parser.parse_args()

    if args.rate_limit <= 0:
        print("Error: Rate limit must be greater than 0", file=sys.stderr)
        sys.exit(1)

    try:
        data = generate_api_key_for_source(
            source=args.source,
            rate_limit=args.rate_limit,
        )
        print_output(data)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGeneration cancelled.", file=sys.stderr)
        sys.exit(1)
