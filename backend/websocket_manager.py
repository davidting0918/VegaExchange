"""
In-memory WebSocket subscription manager for real-time updates.

Channels:
- pool:{symbol} - pool info + recent trades (broadcast on swap / add / remove liquidity)
- user - per-connection user_id (balances, LP updates); broadcast to subscribed user only
- orderbook:{symbol} - orderbook snapshot/diff (broadcast on orderbook changes)

One WebSocket connection can subscribe to multiple channels.
"""

import asyncio
import json
from typing import Any, Optional

from fastapi import WebSocket


class SubscriptionKey:
    """Immutable key for a subscription (channel + optional symbol or user_id)."""

    __slots__ = ("channel", "symbol", "user_id")

    def __init__(
        self,
        channel: str,
        symbol: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.channel = channel
        self.symbol = symbol
        self.user_id = user_id

    def __hash__(self):
        return hash((self.channel, self.symbol or "", self.user_id or ""))

    def __eq__(self, other):
        if not isinstance(other, SubscriptionKey):
            return False
        return (
            self.channel == other.channel
            and (self.symbol or "") == (other.symbol or "")
            and (self.user_id or "") == (other.user_id or "")
        )


class ConnectionState:
    """Per-connection state: subscriptions and optional user_id for auth."""

    __slots__ = ("ws", "user_id", "subscriptions")

    def __init__(self, ws: WebSocket, user_id: Optional[str] = None):
        self.ws = ws
        self.user_id = user_id
        self.subscriptions: set[SubscriptionKey] = set()


# Global registry: SubscriptionKey -> set of ConnectionState
_subscriptions: dict[SubscriptionKey, set[ConnectionState]] = {}
# All active connections for cleanup on disconnect
_connections: set[ConnectionState] = set()
_lock = asyncio.Lock()


async def subscribe(
    conn: ConnectionState,
    channel: str,
    symbol: Optional[str] = None,
    user_id_override: Optional[str] = None,
) -> bool:
    """
    Subscribe a connection to a channel.
    - pool: requires symbol.
    - orderbook: requires symbol.
    - user: no symbol; uses conn.user_id (or user_id_override) to filter broadcasts.
    Returns True if subscription was added.
    """
    if channel == "user":
        uid = user_id_override or conn.user_id
        if not uid:
            return False
        key = SubscriptionKey(channel=channel, user_id=uid)
    elif channel in ("pool", "orderbook") and symbol:
        key = SubscriptionKey(channel=channel, symbol=symbol)
    else:
        return False

    async with _lock:
        if key not in _subscriptions:
            _subscriptions[key] = set()
        _subscriptions[key].add(conn)
        conn.subscriptions.add(key)
    return True


async def unsubscribe(conn: ConnectionState, channel: str, symbol: Optional[str] = None) -> None:
    """Remove one subscription. For user channel, symbol is ignored."""
    if channel == "user":
        key = SubscriptionKey(channel=channel, user_id=conn.user_id)
    else:
        key = SubscriptionKey(channel=channel, symbol=symbol)
    async with _lock:
        conn.subscriptions.discard(key)
        subs = _subscriptions.get(key)
        if subs:
            subs.discard(conn)
            if not subs:
                del _subscriptions[key]


async def register_connection(conn: ConnectionState) -> None:
    async with _lock:
        _connections.add(conn)


async def unregister_connection(conn: ConnectionState) -> None:
    async with _lock:
        _connections.discard(conn)
        for key in list(conn.subscriptions):
            subs = _subscriptions.get(key)
            if subs:
                subs.discard(conn)
                if not subs:
                    del _subscriptions[key]
        conn.subscriptions.clear()


async def _send_json(conn: ConnectionState, payload: dict[str, Any]) -> None:
    try:
        await conn.ws.send_json(payload)
    except Exception:
        pass


async def broadcast_pool(symbol: str, data: dict[str, Any]) -> None:
    """Send payload to all connections subscribed to pool:{symbol}."""
    key = SubscriptionKey(channel="pool", symbol=symbol)
    async with _lock:
        conns = set(_subscriptions.get(key, []))
    msg = {"channel": "pool", "symbol": symbol, "data": data}
    await asyncio.gather(*[_send_json(c, msg) for c in conns])


async def broadcast_user(user_id: str, data: dict[str, Any]) -> None:
    """Send payload to all connections subscribed to user channel for this user_id."""
    key = SubscriptionKey(channel="user", user_id=user_id)
    async with _lock:
        conns = set(_subscriptions.get(key, []))
    msg = {"channel": "user", "data": data}
    await asyncio.gather(*[_send_json(c, msg) for c in conns])


async def broadcast_orderbook(symbol: str, data: dict[str, Any]) -> None:
    """Send payload to all connections subscribed to orderbook:{symbol}."""
    key = SubscriptionKey(channel="orderbook", symbol=symbol)
    async with _lock:
        conns = set(_subscriptions.get(key, []))
    msg = {"channel": "orderbook", "symbol": symbol, "data": data}
    await asyncio.gather(*[_send_json(c, msg) for c in conns])
