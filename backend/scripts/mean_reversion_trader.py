"""
Mean Reversion Trading Strategy - AMM Pool

This strategy trades against price deviations from the moving average.
When price deviates significantly from the mean, it trades in the opposite direction,
expecting price to revert to the mean.

Strategy Logic:
- Calculate moving average of recent prices
- If current price > MA + threshold: SELL (price too high, expect drop)
- If current price < MA - threshold: BUY (price too low, expect rise)
- Trade size proportional to deviation magnitude

Usage:
    python -m backend.scripts.mean_reversion_trader
"""

import os
import sys
import time
from collections import deque
from datetime import datetime
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)

# Configuration
BASE_URL = "http://localhost:8000"
EMAIL = "trader1@vegaexchange.com"
PASSWORD = "Trader1!"
SYMBOL = "VEGA/USDT-USDT:SPOT"
SYMBOL_PATH = "VEGA-USDT-USDT-SPOT"
SWAP_AMOUNT_MIN = 1000
SWAP_AMOUNT_MAX = 50000
INTERVAL_SEC = 2
MA_WINDOW = 20  # Number of prices to use for moving average
DEVIATION_THRESHOLD = 0.02  # 2% deviation from MA triggers trade
MIN_TRADE_SIZE = 1000
MAX_TRADE_SIZE = 50000

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


def get_user_balances(token: str) -> tuple[float, float]:
    """Get base and quote balance. Returns (base_balance, quote_balance)."""
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


def execute_swap(token: str, side: int, amount_in: float) -> dict:
    """Execute AMM swap."""
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


def calculate_moving_average(prices: deque) -> float:
    """Calculate moving average of prices."""
    if len(prices) == 0:
        return 0.0
    return sum(prices) / len(prices)


def calculate_trade_size(deviation_pct: float, available: float) -> float:
    """
    Calculate trade size based on deviation magnitude.
    Larger deviation = larger trade size (up to max).
    """
    # Scale trade size: 0.5% deviation = min trade, 5% deviation = max trade
    deviation_abs = abs(deviation_pct)
    if deviation_abs < 0.005:  # Less than 0.5%
        return 0
    
    # Linear scaling between min and max
    scale = min(1.0, (deviation_abs - 0.005) / 0.045)  # Scale 0.5% to 5%
    trade_size = MIN_TRADE_SIZE + (MAX_TRADE_SIZE - MIN_TRADE_SIZE) * scale
    return min(trade_size, available * 0.1)  # Max 10% of available balance


def main():
    print("=" * 60)
    print("Mean Reversion Trading Strategy")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Email: {EMAIL}")
    print(f"Symbol: {SYMBOL}")
    print(f"MA Window: {MA_WINDOW} prices")
    print(f"Deviation Threshold: {DEVIATION_THRESHOLD * 100:.1f}%")
    print(f"Trade Size Range: {MIN_TRADE_SIZE}-{MAX_TRADE_SIZE}")
    print(f"Check Interval: {INTERVAL_SEC}s")
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
    price_history = deque(maxlen=MA_WINDOW)
    trade_count = 0
    buy_count = 0
    sell_count = 0
    total_buy_amount = 0.0
    total_sell_amount = 0.0
    total_fees_paid = 0.0
    price_impacts = []
    trade_sizes = []
    deviations = []

    try:
        while True:
            try:
                # Get current pool data
                reserve_base, reserve_quote, current_price = get_pool_data()
                base_balance, quote_balance = get_user_balances(token)

                # Add current price to history
                price_history.append(current_price)

                # Need enough history to calculate MA
                if len(price_history) < MA_WINDOW:
                    print(f"[INFO] Building price history ({len(price_history)}/{MA_WINDOW})...")
                    time.sleep(INTERVAL_SEC)
                    continue

                # Calculate moving average
                ma = calculate_moving_average(price_history)
                deviation_pct = (current_price - ma) / ma if ma > 0 else 0

                print(f"[DATA] Price: {current_price:.6f}, MA: {ma:.6f}, Deviation: {deviation_pct*100:+.2f}%")

                # Determine trade direction based on deviation
                side: Optional[int] = None
                trade_size = 0.0

                if deviation_pct > DEVIATION_THRESHOLD:
                    # Price too high: SELL
                    available_sell_value = base_balance * current_price
                    if available_sell_value >= MIN_TRADE_SIZE:
                        side = ORDER_SIDE_SELL
                        trade_size = calculate_trade_size(deviation_pct, available_sell_value)
                        # Convert to base quantity
                        amount_in = trade_size / current_price
                        amount_in = min(amount_in, base_balance)
                        amount_in = round(amount_in, 8)
                        if amount_in < 10:  # Pool minimum
                            side = None
                elif deviation_pct < -DEVIATION_THRESHOLD:
                    # Price too low: BUY
                    if quote_balance >= MIN_TRADE_SIZE:
                        side = ORDER_SIDE_BUY
                        trade_size = calculate_trade_size(abs(deviation_pct), quote_balance)
                        amount_in = trade_size
                    else:
                        side = None

                # Execute trade if conditions met
                if side is not None and trade_size > 0:
                    side_str = "BUY" if side == ORDER_SIDE_BUY else "SELL"
                    
                    if side == ORDER_SIDE_BUY:
                        amount_in = trade_size
                    else:
                        amount_in = trade_size / current_price
                        amount_in = min(amount_in, base_balance)
                        amount_in = round(amount_in, 8)

                    result = execute_swap(token, side, amount_in)
                    trade_count += 1

                    price = result.get("price", 0)
                    qty = result.get("quantity", 0)
                    quote = result.get("quote_amount", 0)
                    impact = result.get("price_impact")
                    fee = result.get("fee_amount", 0)

                    # Update statistics
                    if side == ORDER_SIDE_BUY:
                        buy_count += 1
                        total_buy_amount += float(quote) if quote else 0
                    else:
                        sell_count += 1
                        total_sell_amount += float(quote) if quote else 0
                    
                    if fee:
                        total_fees_paid += float(fee)
                    if impact is not None:
                        price_impacts.append(float(impact))
                    if trade_size > 0:
                        trade_sizes.append(trade_size)
                    deviations.append(abs(deviation_pct) * 100)

                    print(
                        f"[{trade_count}] {side_str} | "
                        f"Deviation: {deviation_pct*100:+.2f}% | "
                        f"Size: {trade_size:.2f} | "
                        f"Price: {price} | "
                        f"Qty: {qty} | "
                        f"Received: {quote} | "
                        f"Impact: {impact}%"
                    )
                else:
                    print(f"[SKIP] No trade signal (deviation: {deviation_pct*100:+.2f}%, threshold: ±{DEVIATION_THRESHOLD*100:.1f}%)")

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
                else:
                    print(f"[ERR] HTTP error: {e}")
            except Exception as e:
                print(f"[ERR] Error: {e}")

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
        print(f"Strategy: Mean Reversion Trading")
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
        
        if deviations:
            print(f"\nDeviation Statistics:")
            print(f"  - Average Deviation: {sum(deviations)/len(deviations):.2f}%")
            print(f"  - Maximum Deviation: {max(deviations):.2f}%")
        
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
        print(f"MA Window: {MA_WINDOW} prices")
        print(f"Deviation Threshold: {DEVIATION_THRESHOLD * 100:.1f}%")
        print(f"Trade Size Range: {MIN_TRADE_SIZE:,.0f} - {MAX_TRADE_SIZE:,.0f} USDT")
        print(f"Check Interval: {INTERVAL_SEC}s")
        print("=" * 80)


if __name__ == "__main__":
    main()
