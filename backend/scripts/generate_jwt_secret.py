#!/usr/bin/env python3
"""
Generate a secure JWT secret key for VegaExchange

Usage:
    python generate_jwt_secret.py
    python generate_jwt_secret.py --length 64
"""

import argparse
import secrets
import sys


def generate_jwt_secret(length: int = 64) -> str:
    """
    Generate a secure random secret key for JWT signing.
    
    Args:
        length: Length of the secret key in bytes (default: 64)
                For HS256, 32-64 bytes (256-512 bits) is recommended.
    
    Returns:
        Hexadecimal string representation of the secret key
    """
    # Generate random bytes
    random_bytes = secrets.token_bytes(length)
    # Convert to hex string
    secret_key = random_bytes.hex()
    return secret_key


def main():
    parser = argparse.ArgumentParser(
        description="Generate a secure JWT secret key"
    )
    parser.add_argument(
        "--length",
        type=int,
        default=64,
        help="Length of the secret key in bytes (default: 64, recommended: 32-64 for HS256)",
    )
    parser.add_argument(
        "--format",
        choices=["hex", "base64", "urlsafe"],
        default="hex",
        help="Output format (default: hex)",
    )
    
    args = parser.parse_args()
    
    # Generate secret
    random_bytes = secrets.token_bytes(args.length)
    
    if args.format == "hex":
        secret_key = random_bytes.hex()
    elif args.format == "base64":
        import base64
        secret_key = base64.b64encode(random_bytes).decode("utf-8")
    elif args.format == "urlsafe":
        import base64
        secret_key = base64.urlsafe_b64encode(random_bytes).decode("utf-8")
    
    # Output
    print("=" * 70)
    print("JWT Secret Key Generated")
    print("=" * 70)
    print(f"\nSecret Key ({args.length} bytes, {args.format} format):")
    print(f"\n{secret_key}\n")
    print("=" * 70)
    print("\nAdd this to your .env file:")
    print(f"JWT_SECRET_KEY={secret_key}\n")
    print("=" * 70)
    
    return secret_key


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGeneration cancelled.", file=sys.stderr)
        sys.exit(1)
