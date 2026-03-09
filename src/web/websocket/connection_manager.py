"""WebSocket connection registry: maps draft_id to connected browser clients."""

import json
import logging
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Thread-safe (asyncio) registry of active WebSocket connections per draft."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, draft_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[draft_id].add(websocket)
        logger.debug(
            "WebSocket connected to draft %s (%d total)",
            draft_id,
            len(self._connections[draft_id]),
        )

    def disconnect(self, draft_id: str, websocket: WebSocket) -> None:
        self._connections[draft_id].discard(websocket)
        logger.debug(
            "WebSocket disconnected from draft %s (%d remaining)",
            draft_id,
            len(self._connections[draft_id]),
        )

    async def broadcast(self, draft_id: str, event: dict) -> None:
        """Send an event JSON to every connected client for this draft."""
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(draft_id, [])):
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[draft_id].discard(ws)

    async def send_to(self, websocket: WebSocket, event: dict) -> None:
        """Send an event to a single WebSocket."""
        await websocket.send_text(json.dumps(event))


# Singleton used across all routers and tasks
manager = ConnectionManager()
