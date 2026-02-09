"""
Continuous Trading Script - AMM Pool Swap Volume Generator

Logs in as a trader and continuously executes small swaps on AMM-USDT-USDT-SPOT
to generate trading volume and cause price volatility.

Usage:
    python -m backend.scripts.continuous_trader
"""

import os
import random
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)

# Hardcoded config
BASE_URL = "http://localhost:8000"
EMAIL = "lp1@vegaexchange.com"
PASSWORD = "Lp1!"
SYMBOL = "VEGA/USDT-USDT:SPOT"
SYMBOL_PATH = "VEGA-USDT-USDT-SPOT"  # For pool API query params
SWAP_AMOUNT_MIN = 1000
SWAP_AMOUNT_MAX = 50000
INTERVAL_SEC = 0

# OrderSide: BUY=0, SELL=1
ORDER_SIDE_BUY = 0
ORDER_SIDE_SELL = 1


def login() -> str:
    """Login and return access token."""
    url = f"{BASE_URL}/api/auth/login/email"
    payload = {"email": EMAIL, "password": PASSWORD}
    with httpx.Client(timeout=10) as client:
        resp = client.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Login failed: {data.get('detail', data)}")
    token = data.get("data", {}).get("access_token")
    if not token:
        raise RuntimeError("No access_token in login response")
    return token


def get_user_balances(token: str) -> tuple[float, float]:
    """Get base and quote balance for the pool. Returns (base_balance, quote_balance)."""
    url = f"{BASE_URL}/api/pool/user"
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, params={"symbol": SYMBOL_PATH}, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Failed to get balances: {data.get('detail', data)}")
    d = data.get("data", {})
    base = float(d.get("base_balance", 0))
    quote = float(d.get("quote_balance", 0))
    return base, quote


def get_pool_data() -> tuple[float, float, float]:
    """Get pool reserves and price. Returns (reserve_base, reserve_quote, current_price)."""
    url = f"{BASE_URL}/api/pool"
    with httpx.Client(timeout=10) as client:
        resp = client.get(url, params={"symbol": SYMBOL_PATH})
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Failed to get pool: {data.get('detail', data)}")
    d = data.get("data", {})
    rb = float(d.get("reserve_base", 0))
    rq = float(d.get("reserve_quote", 0))
    price = float(d.get("current_price", 1)) if rb > 0 else 1.0
    return rb, rq, price


def quote_to_base_quantity(quote_amount: float, reserve_base: float, reserve_quote: float) -> float:
    """Convert quote amount (USDT to receive) to base quantity (AMM to sell). AMM formula."""
    if reserve_quote <= quote_amount:
        return reserve_base * 0.99  # Avoid div by zero
    return quote_amount * reserve_base / (reserve_quote - quote_amount)


def execute_swap(token: str, side: int, amount_in: float) -> dict:
    """Execute AMM swap. side: 0=BUY, 1=SELL. BUY: amount_in=USDT. SELL: amount_in=base quantity."""
    url = f"{BASE_URL}/api/pool/swap"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "symbol": SYMBOL,
        "side": side,
        "amount_in": str(amount_in),
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"Swap failed: {data.get('detail', data.get('data'))}")
    return data.get("data", {})


def main():
    print("=" * 60)
    print("VegaExchange Continuous Trader")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Email: {EMAIL}")
    print(f"Symbol: {SYMBOL}")
    print(f"Amount range (quote USDT): {SWAP_AMOUNT_MIN}-{SWAP_AMOUNT_MAX}")
    print(f"Interval: {INTERVAL_SEC}s")
    print("=" * 60)

    try:
        token = login()
        print(f"[OK] Logged in successfully")
    except Exception as e:
        print(f"[ERR] Login failed: {e}")
        sys.exit(1)

    trade_count = 0
    last_side = ORDER_SIDE_SELL  # Start with BUY next (alternate)

    try:
        while True:
            try:
                # Get balances and pool data
                base_balance, quote_balance = get_user_balances(token)
                reserve_base, reserve_quote, current_price = get_pool_data()

                # Available value in quote terms: quote_balance (for BUY), base*price (for SELL)
                available_buy = quote_balance
                available_sell_value = base_balance * current_price if current_price > 0 else 0

                # Decide side: alternate when both available, else use the only available one
                can_buy = available_buy >= SWAP_AMOUNT_MIN
                can_sell = available_sell_value >= SWAP_AMOUNT_MIN

                if can_buy and can_sell:
                    # Alternate BUY/SELL to create price volatility
                    side = ORDER_SIDE_SELL if last_side == ORDER_SIDE_BUY else ORDER_SIDE_BUY
                elif can_buy:
                    side = ORDER_SIDE_BUY
                elif can_sell:
                    side = ORDER_SIDE_SELL
                else:
                    print(f"[SKIP] Insufficient balance (base={base_balance:.2f}, quote={quote_balance:.2f})")
                    time.sleep(INTERVAL_SEC)
                    continue

                # Amount in quote (USDT) - random between min and max, capped by available
                max_quote = min(SWAP_AMOUNT_MAX, available_buy if side == ORDER_SIDE_BUY else available_sell_value)
                quote_amount = round(random.uniform(SWAP_AMOUNT_MIN, max_quote), 2)

                # Pool min_trade_amount: 10 base or 10 quote
                if side == ORDER_SIDE_BUY:
                    amount_in = quote_amount
                else:
                    amount_in = quote_to_base_quantity(quote_amount, reserve_base, reserve_quote)
                    amount_in = min(amount_in, base_balance)
                    amount_in = round(amount_in, 8)
                    if amount_in < 10:  # Pool min for base
                        print(f"[SKIP] SELL amount too small (base={amount_in:.2f}, min=10)")
                        time.sleep(INTERVAL_SEC)
                        continue

                side_str = "BUY" if side == ORDER_SIDE_BUY else "SELL"

                result = execute_swap(token, side, amount_in)
                trade_count += 1
                last_side = side

                price = result.get("price", "N/A")
                qty = result.get("quantity", "N/A")
                quote = result.get("quote_amount", "N/A")
                impact = result.get("price_impact")
                impact_str = f", impact={impact}" if impact is not None else ""

                print(
                    f"[{trade_count}] {side_str} quote={quote_amount} -> price={price}, qty={qty}, received={quote}{impact_str}"
                )

            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 401:
                    try:
                        token = login()
                        print("[OK] Token refreshed, retrying...")
                        continue
                    except Exception as re:
                        print(f"[ERR] Re-login failed: {re}")
                        sys.exit(1)
                if e.response is not None and e.response.status_code == 400:
                    try:
                        err_data = e.response.json()
                        err_msg = str(err_data.get("detail", err_data))
                    except Exception:
                        err_msg = str(e.response.text or "")
                    print(f"[WARN] {err_msg}")
                print(f"[ERR] HTTP error: {e}")
            except Exception as e:
                print(f"[ERR] Swap failed: {e}")

            time.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n[OK] Stopped by user. Total trades:", trade_count)


if __name__ == "__main__":
    main()
