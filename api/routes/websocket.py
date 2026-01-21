"""WebSocket routes for real-time updates."""

from typing import Dict, Set
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
import json

router = APIRouter()

# Active WebSocket connections per job
_connections: Dict[int, Set[WebSocket]] = {}

# All active connections
_all_connections: Set[WebSocket] = set()


class ConnectionManager:
    """Manage WebSocket connections."""

    def __init__(self):
        self.active_connections: Dict[int, Set[WebSocket]] = {}
        self.all_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, job_id: int = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.all_connections.add(websocket)

        if job_id:
            if job_id not in self.active_connections:
                self.active_connections[job_id] = set()
            self.active_connections[job_id].add(websocket)

        logger.info(f"WebSocket connected (job_id={job_id})")

    def disconnect(self, websocket: WebSocket, job_id: int = None):
        """Remove a WebSocket connection."""
        self.all_connections.discard(websocket)

        if job_id and job_id in self.active_connections:
            self.active_connections[job_id].discard(websocket)
            if not self.active_connections[job_id]:
                del self.active_connections[job_id]

        logger.info(f"WebSocket disconnected (job_id={job_id})")

    async def broadcast_to_job(self, job_id: int, message: dict):
        """Send message to all connections watching a specific job."""
        if job_id not in self.active_connections:
            return

        message_json = json.dumps(message, default=str)
        disconnected = set()

        for connection in self.active_connections[job_id]:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn, job_id)

    async def broadcast_to_all(self, message: dict):
        """Send message to all connections."""
        message_json = json.dumps(message, default=str)
        disconnected = set()

        for connection in self.all_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for all real-time updates.

    Send {"action": "subscribe", "job_id": 123} to subscribe to job updates.
    """
    await manager.connect(websocket)
    subscribed_job_id = None

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # Handle subscription to specific job
                if message.get("action") == "subscribe" and "job_id" in message:
                    job_id = int(message["job_id"])

                    # Unsubscribe from previous job if any
                    if subscribed_job_id:
                        manager.disconnect(websocket, subscribed_job_id)

                    # Subscribe to new job
                    if job_id not in manager.active_connections:
                        manager.active_connections[job_id] = set()
                    manager.active_connections[job_id].add(websocket)
                    subscribed_job_id = job_id

                    await websocket.send_text(json.dumps({
                        "type": "subscribed",
                        "job_id": job_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    }))

                # Handle ping
                elif message.get("action") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    }))

            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON",
                }))

    except WebSocketDisconnect:
        manager.disconnect(websocket, subscribed_job_id)


@router.websocket("/ws/job/{job_id}")
async def job_websocket_endpoint(websocket: WebSocket, job_id: int):
    """
    WebSocket endpoint for specific job updates.

    Automatically subscribes to the specified job.
    """
    await manager.connect(websocket, job_id)

    try:
        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)

                # Handle ping
                if message.get("action") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "job_id": job_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    }))

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        manager.disconnect(websocket, job_id)


def broadcast_job_update(job_id: int, event_type: str, data: dict):
    """
    Broadcast an update for a job.

    This function is synchronous and can be called from background tasks.
    It schedules the async broadcast to run.
    """
    import asyncio

    message = {
        "type": event_type,
        "job_id": job_id,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Schedule the coroutine to run in the existing loop
            asyncio.ensure_future(manager.broadcast_to_job(job_id, message))
        else:
            # Run in a new loop
            loop.run_until_complete(manager.broadcast_to_job(job_id, message))

    except Exception as e:
        logger.debug(f"WebSocket broadcast failed: {e}")


def broadcast_all(event_type: str, data: dict):
    """Broadcast to all connected clients."""
    import asyncio

    message = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            asyncio.ensure_future(manager.broadcast_to_all(message))
        else:
            loop.run_until_complete(manager.broadcast_to_all(message))

    except Exception as e:
        logger.debug(f"WebSocket broadcast failed: {e}")
