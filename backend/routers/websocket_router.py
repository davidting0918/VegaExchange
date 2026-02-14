"""
WebSocket endpoint for real-time updates.

Client connects to GET /ws?token=<jwt> (token optional; required for user channel).
Client sends JSON messages:
  { "action": "subscribe", "channel": "pool", "symbol": "AMM/USDT-USDT:SPOT" }
  { "action": "subscribe", "channel": "user" }
  { "action": "subscribe", "channel": "orderbook", "symbol": "..." }
  { "action": "unsubscribe", "channel": "pool", "symbol": "..." }
"""

import json
from typing import Any, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.core.jwt import verify_token
from backend.websocket_manager import (
    ConnectionState,
    register_connection,
    subscribe as ws_subscribe,
    unregister_connection,
    unsubscribe as ws_unsubscribe,
)

router = APIRouter(tags=["websocket"])


async def _get_user_id_from_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    payload = verify_token(token, token_type="access")
    if not payload:
        return None
    return payload.get("sub") or payload.get("user_id")


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT for user channel; optional for pool/orderbook"),
):
    await websocket.accept()
    user_id = await _get_user_id_from_token(token)
    conn = ConnectionState(ws=websocket, user_id=user_id)
    await register_connection(conn)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            action = msg.get("action")
            if action == "subscribe":
                channel = msg.get("channel")
                symbol = msg.get("symbol")
                if not channel:
                    await websocket.send_json({"error": "subscribe requires channel"})
                    continue
                if channel == "user" and not user_id:
                    await websocket.send_json({"error": "user channel requires authentication"})
                    continue
                ok = await ws_subscribe(conn, channel, symbol=symbol)
                if ok:
                    await websocket.send_json({"ok": True, "subscribed": channel, "symbol": symbol})
                else:
                    await websocket.send_json(
                        {"error": "subscribe failed", "channel": channel, "symbol": symbol}
                    )
            elif action == "unsubscribe":
                channel = msg.get("channel")
                symbol = msg.get("symbol")
                if not channel:
                    await websocket.send_json({"error": "unsubscribe requires channel"})
                    continue
                await ws_unsubscribe(conn, channel, symbol=symbol)
                await websocket.send_json({"ok": True, "unsubscribed": channel, "symbol": symbol})
            else:
                await websocket.send_json({"error": f"Unknown action: {action}"})
    except WebSocketDisconnect:
        pass
    finally:
        await unregister_connection(conn)
