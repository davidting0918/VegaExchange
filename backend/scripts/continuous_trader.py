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
from datetime import datetime

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
SWAP_AMOUNT_MAX = 500000
INTERVAL_SEC = 5

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

    # Get initial balances for P&L calculation
    try:
        initial_base, initial_quote = get_user_balances(token)
        _, _, initial_price = get_pool_data()
        initial_portfolio_value = initial_base * initial_price + initial_quote
    except Exception as e:
        print(f"[WARN] Could not get initial balances: {e}")
        initial_base = initial_quote = initial_price = initial_portfolio_value = 0.0

    # Statistics tracking
    start_time = datetime.now()
    trade_count = 0
    buy_count = 0
    sell_count = 0
    total_buy_amount = 0.0
    total_sell_amount = 0.0
    total_fees_paid = 0.0
    price_impacts = []
    trade_sizes = []
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

                # Decide side: randomly choose when both available, else use the only available one
                can_buy = available_buy >= SWAP_AMOUNT_MIN
                can_sell = available_sell_value >= SWAP_AMOUNT_MIN

                if can_buy and can_sell:
                    # Randomly choose BUY or SELL to create price volatility
                    side = random.choice([ORDER_SIDE_BUY, ORDER_SIDE_SELL])
                elif can_buy:
                    side = ORDER_SIDE_BUY
                elif can_sell:
                    side = ORDER_SIDE_SELL
                else:
                    print(f"[SKIP] Insufficient balance (base={base_balance:.2f}, quote={quote_balance:.2f})")
                    time.sleep(INTERVAL_SEC)
                    continue

                # Amount in quote (USDT) - randomly choose between min and max, capped by available
                max_quote = min(SWAP_AMOUNT_MAX, available_buy if side == ORDER_SIDE_BUY else available_sell_value)
                
                # Ensure we have enough range for random selection
                if max_quote < SWAP_AMOUNT_MIN:
                    print(f"[SKIP] Insufficient balance for minimum trade size (available={max_quote:.2f}, min={SWAP_AMOUNT_MIN})")
                    time.sleep(INTERVAL_SEC)
                    continue
                
                # Randomly choose quote amount: use uniform distribution for better randomness
                quote_amount = round(random.uniform(SWAP_AMOUNT_MIN, max_quote), 2)
                
                # Ensure quote_amount is at least the minimum
                if quote_amount < SWAP_AMOUNT_MIN:
                    quote_amount = SWAP_AMOUNT_MIN

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

                price = result.get("price", 0)
                qty = result.get("quantity", 0)
                quote = result.get("quote_amount", 0)
                impact = result.get("price_impact")
                fee = result.get("fee_amount", 0)

                # Update statistics
                if side == ORDER_SIDE_BUY:
                    buy_count += 1
                    total_buy_amount += float(quote_amount) if quote_amount else 0
                else:
                    sell_count += 1
                    total_sell_amount += float(quote_amount) if quote_amount else 0
                
                if fee:
                    total_fees_paid += float(fee)
                if impact is not None:
                    price_impacts.append(float(impact))
                if quote_amount > 0:
                    trade_sizes.append(quote_amount)

                impact_str = f", impact={impact}%" if impact is not None else ""

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
        # Get final balances
        try:
            final_base, final_quote = get_user_balances(token)
            _, _, final_price = get_pool_data()
            final_portfolio_value = final_base * final_price + final_quote
        except Exception as e:
            print(f"[WARN] Could not get final balances: {e}")
            final_base = final_quote = final_price = final_portfolio_value = 0.0

        # Calculate runtime
        end_time = datetime.now()
        runtime = end_time - start_time
        runtime_seconds = runtime.total_seconds()
        runtime_str = f"{int(runtime_seconds // 3600)}h {int((runtime_seconds % 3600) // 60)}m {int(runtime_seconds % 60)}s"

        # Calculate P&L
        pnl = final_portfolio_value - initial_portfolio_value
        pnl_pct = (pnl / initial_portfolio_value * 100) if initial_portfolio_value > 0 else 0

        # Print comprehensive report
        print("\n" + "=" * 80)
        print("TRADING STRATEGY REPORT")
        print("=" * 80)
        print(f"Strategy: Continuous Random Trading (Volume Generator)")
        print(f"Symbol: {SYMBOL}")
        print(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Runtime: {runtime_str}")
        print("-" * 80)
        print("TRADE STATISTICS")
        print("-" * 80)
        print(f"Total Trades: {trade_count}")
        if trade_count > 0:
            print(f"  - BUY Orders: {buy_count} ({buy_count/trade_count*100:.1f}%)")
            print(f"  - SELL Orders: {sell_count} ({sell_count/trade_count*100:.1f}%)")
        else:
            print(f"  - BUY Orders: 0")
            print(f"  - SELL Orders: 0")
        print(f"Total Buy Volume: {total_buy_amount:,.2f} USDT")
        print(f"Total Sell Volume: {total_sell_amount:,.2f} USDT")
        print(f"Total Trading Volume: {total_buy_amount + total_sell_amount:,.2f} USDT")
        print(f"Total Fees Paid: {total_fees_paid:,.2f} USDT")
        
        if trade_sizes:
            print(f"\nTrade Size Statistics:")
            print(f"  - Average: {sum(trade_sizes)/len(trade_sizes):,.2f} USDT")
            print(f"  - Minimum: {min(trade_sizes):,.2f} USDT")
            print(f"  - Maximum: {max(trade_sizes):,.2f} USDT")
        
        if price_impacts:
            print(f"\nPrice Impact Statistics:")
            print(f"  - Average: {sum(price_impacts)/len(price_impacts):.4f}%")
            print(f"  - Minimum: {min(price_impacts):.4f}%")
            print(f"  - Maximum: {max(price_impacts):.4f}%")
        
        if trade_count > 0:
            avg_trades_per_hour = (trade_count / runtime_seconds) * 3600 if runtime_seconds > 0 else 0
            print(f"\nTrading Frequency:")
            print(f"  - Average Trades per Hour: {avg_trades_per_hour:.2f}")
            print(f"  - Average Time between Trades: {runtime_seconds/trade_count:.1f}s")
        
        print("-" * 80)
        print("PORTFOLIO PERFORMANCE")
        print("-" * 80)
        print(f"Initial Portfolio Value: {initial_portfolio_value:,.2f} USDT")
        print(f"  - Base: {initial_base:.6f} @ {initial_price:.6f} = {initial_base * initial_price:,.2f} USDT")
        print(f"  - Quote: {initial_quote:,.2f} USDT")
        print(f"\nFinal Portfolio Value: {final_portfolio_value:,.2f} USDT")
        print(f"  - Base: {final_base:.6f} @ {final_price:.6f} = {final_base * final_price:,.2f} USDT")
        print(f"  - Quote: {final_quote:,.2f} USDT")
        print(f"\nProfit/Loss: {pnl:+,.2f} USDT ({pnl_pct:+.2f}%)")
        print("-" * 80)
        print("STRATEGY SETTINGS")
        print("-" * 80)
        print(f"Trade Amount Range: {SWAP_AMOUNT_MIN:,.0f} - {SWAP_AMOUNT_MAX:,.0f} USDT")
        print(f"Trading Interval: {INTERVAL_SEC}s")
        print(f"Side Selection: Random (when both BUY/SELL available)")
        print("=" * 80)


if __name__ == "__main__":
    main()
