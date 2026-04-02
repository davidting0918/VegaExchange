"""
WebSocket Connection Manager

Manages channel-based WebSocket subscriptions and message broadcasting.
Singleton pattern consistent with db_manager.py.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Module-level singleton
_ws_manager: Optional["ConnectionManager"] = None


def get_ws_manager() -> Optional["ConnectionManager"]:
    """Get the global WebSocket manager instance."""
    return _ws_manager


def init_ws_manager() -> "ConnectionManager":
    """Initialize the global WebSocket manager."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = ConnectionManager()
    return _ws_manager


class ConnectionManager:
    """
    Channel-based WebSocket connection manager.

    Supports:
    - Public channels: orderbook:{symbol}, trades:{symbol}, ticker:{symbol}
    - Private channels: user:{user_id} (requires authentication)
    - Heartbeat ping/pong
    """

    def __init__(self):
        # channel_name -> set of WebSocket connections
        self._subscriptions: Dict[str, Set[WebSocket]] = {}
        # websocket -> set of subscribed channel names (for cleanup)
        self._connection_channels: Dict[WebSocket, Set[str]] = {}
        # websocket -> user_id (for authenticated connections)
        self._authenticated: Dict[WebSocket, str] = {}

    @property
    def connection_count(self) -> int:
        return len(self._connection_channels)

    def register(self, ws: WebSocket, user_id: Optional[str] = None):
        """Register a new WebSocket connection."""
        self._connection_channels[ws] = set()
        if user_id:
            self._authenticated[ws] = user_id

    def unregister(self, ws: WebSocket):
        """Remove a WebSocket connection and all its subscriptions."""
        channels = self._connection_channels.pop(ws, set())
        for channel in channels:
            subs = self._subscriptions.get(channel)
            if subs:
                subs.discard(ws)
                if not subs:
                    del self._subscriptions[channel]
        self._authenticated.pop(ws, None)

    def subscribe(self, ws: WebSocket, channel: str) -> bool:
        """
        Subscribe a connection to a channel.

        Returns False if the channel requires auth and the connection is not authenticated.
        """
        # Private channels require authentication
        if channel.startswith("user:"):
            user_id = self._authenticated.get(ws)
            if not user_id:
                return False
            # Users can only subscribe to their own channel
            expected_user_id = channel.split(":", 1)[1]
            if user_id != expected_user_id:
                return False

        if channel not in self._subscriptions:
            self._subscriptions[channel] = set()
        self._subscriptions[channel].add(ws)
        self._connection_channels.setdefault(ws, set()).add(channel)
        return True

    def unsubscribe(self, ws: WebSocket, channel: str):
        """Unsubscribe a connection from a channel."""
        subs = self._subscriptions.get(channel)
        if subs:
            subs.discard(ws)
            if not subs:
                del self._subscriptions[channel]
        channels = self._connection_channels.get(ws)
        if channels:
            channels.discard(channel)

    async def broadcast(self, channel: str, data: Any):
        """Broadcast a message to all subscribers of a channel."""
        subs = self._subscriptions.get(channel)
        if not subs:
            return

        message = json.dumps({"channel": channel, "data": data})
        stale: list[WebSocket] = []

        for ws in subs:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        # Clean up disconnected clients
        for ws in stale:
            self.unregister(ws)

    async def send_to_user(self, user_id: str, data: Any):
        """Send a message to a specific user's private channel."""
        await self.broadcast(f"user:{user_id}", data)

    async def handle_client(self, ws: WebSocket, user_id: Optional[str] = None):
        """
        Main loop for handling a single WebSocket client.

        Processes subscribe/unsubscribe messages and sends heartbeat pings.
        """
        self.register(ws, user_id)
        try:
            while True:
                try:
                    raw = await asyncio.wait_for(ws.receive_text(), timeout=60)
                except asyncio.TimeoutError:
                    # Send heartbeat ping
                    try:
                        await ws.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        break
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await ws.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                    continue

                action = msg.get("action")
                channel = msg.get("channel", "")

                if action == "subscribe":
                    ok = self.subscribe(ws, channel)
                    await ws.send_text(json.dumps({
                        "type": "subscribed" if ok else "error",
                        "channel": channel,
                        "message": None if ok else "Unauthorized for this channel",
                    }))
                elif action == "unsubscribe":
                    self.unsubscribe(ws, channel)
                    await ws.send_text(json.dumps({
                        "type": "unsubscribed",
                        "channel": channel,
                    }))
                elif action == "pong":
                    pass  # Client responded to our ping
                else:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    }))

        except Exception:
            pass  # Connection closed or errored
        finally:
            self.unregister(ws)
