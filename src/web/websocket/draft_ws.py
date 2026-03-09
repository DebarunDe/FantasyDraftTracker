"""WebSocket endpoint: /ws/{draft_id}

Clients connect here to receive live pick events (server-push only).
Human picks are still sent via HTTP POST — WebSocket is read-only from the
client's perspective.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.web.websocket.connection_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/{draft_id}")
async def websocket_endpoint(websocket: WebSocket, draft_id: str) -> None:
    await manager.connect(draft_id, websocket)
    try:
        while True:
            # Keep connection alive; handle client pongs and join messages.
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                msg = json.loads(raw)
                if msg.get("type") == "pong":
                    pass  # heartbeat ack — no response needed
            except asyncio.TimeoutError:
                # Send a ping to detect stale connections
                await manager.send_to(websocket, {"type": "ping"})
            except (json.JSONDecodeError, KeyError):
                pass  # Ignore malformed client messages
    except WebSocketDisconnect:
        manager.disconnect(draft_id, websocket)
        logger.debug("WebSocket disconnect for draft %s", draft_id)
    except Exception as exc:
        manager.disconnect(draft_id, websocket)
        logger.warning("WebSocket error for draft %s: %s", draft_id, exc)
