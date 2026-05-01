"""
WebSocket connection manager.

Keeps track of all connected clients and provides a broadcast helper.
"""
import asyncio
import json
import logging
from typing import List

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._active.append(websocket)
        log.info("WS client connected  (total: %d)", len(self._active))

    def disconnect(self, websocket: WebSocket):
        self._active = [ws for ws in self._active if ws is not websocket]
        log.info("WS client disconnected (total: %d)", len(self._active))

    async def broadcast(self, message: dict):
        """Send a JSON message to every connected client (skip dead sockets)."""
        text = json.dumps(message)
        dead = []
        for ws in self._active:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
