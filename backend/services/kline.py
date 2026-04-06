"""
Kline service — pre-computed candlestick management.

Handles:
- Trade-time upsert: 8 intervals updated per trade
- Startup backfill: forward-fill gaps on server restart
- Initial klines: written on symbol/pool creation
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from backend.core.db_manager import get_db

# Supported intervals and their duration in seconds
SUPPORTED_INTERVALS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
    "1M": None,  # handled specially (calendar month)
}

INTERVAL_SECONDS = {k: v for k, v in SUPPORTED_INTERVALS.items() if v is not None}


def _floor_to_interval(ts: datetime, interval: str) -> datetime:
    """Floor a timestamp to the start of its interval bucket."""
    ts_utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    if interval == "1M":
        return ts_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    seconds = INTERVAL_SECONDS[interval]
    epoch = int(ts_utc.timestamp())
    floored_epoch = (epoch // seconds) * seconds
    return datetime.fromtimestamp(floored_epoch, tz=timezone.utc)


async def upsert_klines(
    symbol_id: int,
    engine_type: int,
    price: Decimal,
    quantity: Decimal,
    quote_amount: Decimal,
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Upsert kline candles for all 8 intervals after a trade.
    Uses INSERT ON CONFLICT DO UPDATE for atomic upsert.
    """
    db = get_db()
    ts = timestamp or datetime.now(timezone.utc)

    for interval in SUPPORTED_INTERVALS:
        open_time = _floor_to_interval(ts, interval)

        await db.execute(
            """
            INSERT INTO klines (symbol_id, engine_type, interval, open_time, open, high, low, close, volume, quote_volume, trade_count)
            VALUES ($1, $2, $3, $4, $5, $5, $5, $5, $6, $7, 1)
            ON CONFLICT (symbol_id, engine_type, interval, open_time) DO UPDATE SET
                high = GREATEST(klines.high, EXCLUDED.high),
                low = LEAST(klines.low, EXCLUDED.low),
                close = EXCLUDED.close,
                volume = klines.volume + EXCLUDED.volume,
                quote_volume = klines.quote_volume + EXCLUDED.quote_volume,
                trade_count = klines.trade_count + 1
            """,
            symbol_id,
            engine_type,
            interval,
            open_time,
            price,
            quantity,
            quote_amount,
        )


async def write_initial_klines(
    symbol_id: int,
    engine_type: int,
    price: Decimal,
    timestamp: Optional[datetime] = None,
) -> None:
    """
    Write initial kline candles for all 8 intervals when creating a symbol/pool.
    Sets OHLCV = price with volume=0, trade_count=0.
    """
    db = get_db()
    ts = timestamp or datetime.now(timezone.utc)

    for interval in SUPPORTED_INTERVALS:
        open_time = _floor_to_interval(ts, interval)

        await db.execute(
            """
            INSERT INTO klines (symbol_id, engine_type, interval, open_time, open, high, low, close, volume, quote_volume, trade_count)
            VALUES ($1, $2, $3, $4, $5, $5, $5, $5, 0, 0, 0)
            ON CONFLICT (symbol_id, engine_type, interval, open_time) DO NOTHING
            """,
            symbol_id,
            engine_type,
            interval,
            open_time,
            price,
        )


async def kline_backfill() -> None:
    """
    On server startup, scan all symbol × interval for gaps and forward-fill
    with flat candles (OHLCV = prev close, volume=0).
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    # Get all active symbols with their engine types
    symbols = await db.read(
        "SELECT symbol_id, engine_type FROM symbol_configs WHERE is_active = TRUE"
    )

    total_filled = 0

    for sym in symbols:
        symbol_id = sym["symbol_id"]
        engine_type = sym["engine_type"]

        for interval, seconds in INTERVAL_SECONDS.items():
            # Get the last kline for this symbol + interval
            last = await db.read_one(
                """
                SELECT open_time, close FROM klines
                WHERE symbol_id = $1 AND engine_type = $2 AND interval = $3
                ORDER BY open_time DESC LIMIT 1
                """,
                symbol_id, engine_type, interval,
            )

            if not last:
                continue

            last_open = last["open_time"]
            if last_open.tzinfo is None:
                last_open = last_open.replace(tzinfo=timezone.utc)
            prev_close = last["close"]

            # Generate missing candles from last_open + interval to now
            current = datetime.fromtimestamp(
                int(last_open.timestamp()) + seconds, tz=timezone.utc
            )

            batch_values = []
            while current <= now:
                batch_values.append((symbol_id, engine_type, interval, current, prev_close))
                current = datetime.fromtimestamp(
                    int(current.timestamp()) + seconds, tz=timezone.utc
                )

            # Batch insert forward-fill candles
            for sv in batch_values:
                await db.execute(
                    """
                    INSERT INTO klines (symbol_id, engine_type, interval, open_time, open, high, low, close, volume, quote_volume, trade_count)
                    VALUES ($1, $2, $3, $4, $5, $5, $5, $5, 0, 0, 0)
                    ON CONFLICT (symbol_id, engine_type, interval, open_time) DO NOTHING
                    """,
                    sv[0], sv[1], sv[2], sv[3], sv[4],
                )

            total_filled += len(batch_values)

        # Handle 1M interval separately
        last_month = await db.read_one(
            """
            SELECT open_time, close FROM klines
            WHERE symbol_id = $1 AND engine_type = $2 AND interval = '1M'
            ORDER BY open_time DESC LIMIT 1
            """,
            symbol_id, engine_type,
        )

        if last_month:
            last_open = last_month["open_time"]
            if last_open.tzinfo is None:
                last_open = last_open.replace(tzinfo=timezone.utc)
            prev_close = last_month["close"]

            # Advance month by month
            current_year = last_open.year
            current_month = last_open.month + 1
            if current_month > 12:
                current_year += 1
                current_month = 1

            while datetime(current_year, current_month, 1, tzinfo=timezone.utc) <= now:
                open_time = datetime(current_year, current_month, 1, tzinfo=timezone.utc)
                await db.execute(
                    """
                    INSERT INTO klines (symbol_id, engine_type, interval, open_time, open, high, low, close, volume, quote_volume, trade_count)
                    VALUES ($1, $2, '1M', $3, $4, $4, $4, $4, 0, 0, 0)
                    ON CONFLICT (symbol_id, engine_type, interval, open_time) DO NOTHING
                    """,
                    symbol_id, engine_type, open_time, prev_close,
                )
                total_filled += 1
                current_month += 1
                if current_month > 12:
                    current_year += 1
                    current_month = 1

    print(f"Kline backfill complete: {total_filled} candles filled.")


async def get_klines(
    symbol_id: int,
    engine_type: int,
    interval: str,
    limit: int = 100,
) -> List[dict]:
    """Get klines from pre-computed table."""
    if interval not in SUPPORTED_INTERVALS:
        return []

    db = get_db()
    rows = await db.read(
        """
        SELECT open_time, open, high, low, close, volume, quote_volume, trade_count
        FROM klines
        WHERE symbol_id = $1 AND engine_type = $2 AND interval = $3
        ORDER BY open_time DESC
        LIMIT $4
        """,
        symbol_id, engine_type, interval, limit,
    )

    # Reverse to ascending order for chart rendering
    rows.reverse()
    return rows


async def get_24h_ticker(symbol_id: int, engine_type: int) -> dict:
    """
    Get 24h ticker stats from 1h klines (24 rows).
    Returns: open_24h, high_24h, low_24h, close (current), volume_24h, quote_volume_24h, price_change, price_change_pct.
    """
    db = get_db()

    rows = await db.read(
        """
        SELECT open_time, open, high, low, close, volume, quote_volume
        FROM klines
        WHERE symbol_id = $1 AND engine_type = $2 AND interval = '1h'
        ORDER BY open_time DESC
        LIMIT 24
        """,
        symbol_id, engine_type,
    )

    if not rows:
        return {
            "open_24h": 0, "high_24h": 0, "low_24h": 0, "close": 0,
            "volume_24h": 0, "quote_volume_24h": 0,
            "price_change": 0, "price_change_pct": 0,
        }

    # rows are DESC, so rows[0] is latest, rows[-1] is oldest
    current_close = float(rows[0]["close"])
    open_24h = float(rows[-1]["open"])
    high_24h = max(float(r["high"]) for r in rows)
    low_24h = min(float(r["low"]) for r in rows)
    volume_24h = sum(float(r["volume"]) for r in rows)
    quote_volume_24h = sum(float(r["quote_volume"]) for r in rows)

    price_change = current_close - open_24h
    price_change_pct = (price_change / open_24h * 100) if open_24h != 0 else 0

    return {
        "open_24h": open_24h,
        "high_24h": high_24h,
        "low_24h": low_24h,
        "close": current_close,
        "volume_24h": volume_24h,
        "quote_volume_24h": quote_volume_24h,
        "price_change": price_change,
        "price_change_pct": round(price_change_pct, 4),
    }
