"""
Market domain models — kline intervals, market info.
"""

# Interval name → seconds mapping for kline aggregation
KLINE_INTERVALS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}
