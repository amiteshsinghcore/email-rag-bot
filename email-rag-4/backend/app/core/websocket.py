"""
WebSocket Manager

Provides WebSocket connection management, channel subscriptions, and message broadcasting.
Integrates with Redis pub/sub for cross-instance communication.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.cache import cache
from app.core.security import verify_access_token


class MessageType(str, Enum):
    """WebSocket message types."""

    # Connection
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"

    # Task updates
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # RAG streaming
    RAG_CHUNK = "rag_chunk"
    RAG_COMPLETE = "rag_complete"
    RAG_ERROR = "rag_error"

    # Notifications
    NOTIFICATION = "notification"

    # Subscriptions
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"


@dataclass
class WebSocketMessage:
    """WebSocket message structure."""

    type: MessageType | str
    data: dict[str, Any] = field(default_factory=dict)
    channel: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value if isinstance(self.type, MessageType) else self.type,
            "data": self.data,
            "channel": self.channel,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class Connection:
    """Represents a single WebSocket connection."""

    websocket: WebSocket
    user_id: str
    user_role: str | None = None
    subscriptions: set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=lambda: datetime.now())

    def __hash__(self) -> int:
        return id(self.websocket)


class WebSocketManager:
    """
    Manages WebSocket connections and message routing.

    Features:
    - Connection tracking per user
    - Channel-based subscriptions
    - Redis pub/sub for multi-instance support
    - Automatic reconnection handling
    - Message broadcasting
    """

    def __init__(self) -> None:
        """Initialize WebSocket manager."""
        # Active connections by user_id
        self._connections: dict[str, set[Connection]] = {}

        # Channel subscribers
        self._channels: dict[str, set[Connection]] = {}

        # Message handlers
        self._handlers: dict[str, Callable[[Connection, dict], Awaitable[None]]] = {}

        # Redis subscription task
        self._redis_task: asyncio.Task | None = None
        self._running = False

    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return sum(len(conns) for conns in self._connections.values())

    @property
    def user_count(self) -> int:
        """Get number of unique connected users."""
        return len(self._connections)

    async def start(self) -> None:
        """Start the WebSocket manager and Redis listener."""
        if self._running:
            return

        self._running = True
        self._redis_task = asyncio.create_task(self._listen_redis())
        logger.info("WebSocket manager started")

    async def stop(self) -> None:
        """Stop the WebSocket manager."""
        self._running = False

        if self._redis_task:
            self._redis_task.cancel()
            try:
                await self._redis_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for user_connections in list(self._connections.values()):
            for conn in list(user_connections):
                await self._close_connection(conn, "Server shutdown")

        logger.info("WebSocket manager stopped")

    async def authenticate(self, websocket: WebSocket) -> tuple[str, str | None] | None:
        """
        Authenticate a WebSocket connection using JWT token.

        Token can be passed as:
        - Query parameter: ?token=xxx
        - Header: Authorization: Bearer xxx

        Returns:
            Tuple of (user_id, role) if authenticated, None otherwise
        """
        # Try query parameter first
        token = websocket.query_params.get("token")

        # Try Authorization header
        if not token:
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]

        if not token:
            return None

        # Verify token
        payload = verify_access_token(token)
        if not payload:
            return None

        return payload.sub, payload.role

    async def connect(
        self,
        websocket: WebSocket,
        user_id: str,
        user_role: str | None = None,
    ) -> Connection:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket connection
            user_id: Authenticated user ID
            user_role: User role for permissions

        Returns:
            The Connection object
        """
        await websocket.accept()

        connection = Connection(
            websocket=websocket,
            user_id=user_id,
            user_role=user_role,
        )

        # Add to user connections
        if user_id not in self._connections:
            self._connections[user_id] = set()
        self._connections[user_id].add(connection)

        # Subscribe to user-specific channel
        await self.subscribe(connection, f"user:{user_id}")

        # Send connected message
        await self.send(
            connection,
            WebSocketMessage(
                type=MessageType.CONNECTED,
                data={
                    "user_id": user_id,
                    "connection_id": id(websocket),
                },
            ),
        )

        logger.info(f"WebSocket connected: user={user_id}, connections={self.connection_count}")
        return connection

    async def disconnect(self, connection: Connection) -> None:
        """
        Handle WebSocket disconnection.

        Args:
            connection: The connection to disconnect
        """
        user_id = connection.user_id

        # Remove from channels
        for channel in list(connection.subscriptions):
            await self.unsubscribe(connection, channel)

        # Remove from user connections
        if user_id in self._connections:
            self._connections[user_id].discard(connection)
            if not self._connections[user_id]:
                del self._connections[user_id]

        logger.info(f"WebSocket disconnected: user={user_id}, connections={self.connection_count}")

    async def subscribe(self, connection: Connection, channel: str) -> None:
        """
        Subscribe a connection to a channel.

        Args:
            connection: The connection to subscribe
            channel: Channel name to subscribe to
        """
        if channel not in self._channels:
            self._channels[channel] = set()

        self._channels[channel].add(connection)
        connection.subscriptions.add(channel)

        logger.debug(f"Subscribed user={connection.user_id} to channel={channel}")

    async def unsubscribe(self, connection: Connection, channel: str) -> None:
        """
        Unsubscribe a connection from a channel.

        Args:
            connection: The connection to unsubscribe
            channel: Channel name to unsubscribe from
        """
        if channel in self._channels:
            self._channels[channel].discard(connection)
            if not self._channels[channel]:
                del self._channels[channel]

        connection.subscriptions.discard(channel)
        logger.debug(f"Unsubscribed user={connection.user_id} from channel={channel}")

    async def send(self, connection: Connection, message: WebSocketMessage) -> bool:
        """
        Send a message to a specific connection.

        Args:
            connection: The target connection
            message: The message to send

        Returns:
            True if sent successfully
        """
        try:
            await connection.websocket.send_text(message.to_json())
            return True
        except WebSocketDisconnect:
            await self.disconnect(connection)
            return False
        except Exception as e:
            logger.error(f"Failed to send WebSocket message: {e}")
            return False

    async def send_to_user(self, user_id: str, message: WebSocketMessage) -> int:
        """
        Send a message to all connections of a user.

        Args:
            user_id: Target user ID
            message: The message to send

        Returns:
            Number of connections that received the message
        """
        connections = self._connections.get(user_id, set())
        sent = 0

        for conn in list(connections):
            if await self.send(conn, message):
                sent += 1

        return sent

    async def broadcast_to_channel(
        self,
        channel: str,
        message: WebSocketMessage,
    ) -> int:
        """
        Broadcast a message to all subscribers of a channel.

        Args:
            channel: Target channel
            message: The message to send

        Returns:
            Number of connections that received the message
        """
        message.channel = channel
        connections = self._channels.get(channel, set())
        sent = 0

        for conn in list(connections):
            if await self.send(conn, message):
                sent += 1

        return sent

    async def broadcast_all(self, message: WebSocketMessage) -> int:
        """
        Broadcast a message to all connected users.

        Args:
            message: The message to send

        Returns:
            Number of connections that received the message
        """
        sent = 0

        for user_connections in list(self._connections.values()):
            for conn in list(user_connections):
                if await self.send(conn, message):
                    sent += 1

        return sent

    def register_handler(
        self,
        message_type: str,
        handler: Callable[[Connection, dict], Awaitable[None]],
    ) -> None:
        """
        Register a handler for a specific message type.

        Args:
            message_type: The message type to handle
            handler: Async function to call with (connection, data)
        """
        self._handlers[message_type] = handler

    async def handle_message(self, connection: Connection, raw_message: str) -> None:
        """
        Handle an incoming WebSocket message.

        Args:
            connection: The source connection
            raw_message: Raw JSON message string
        """
        try:
            data = json.loads(raw_message)
            message_type = data.get("type", "")

            # Handle ping/pong
            if message_type == "ping":
                await self.send(
                    connection,
                    WebSocketMessage(type=MessageType.PONG),
                )
                return

            # Handle subscribe/unsubscribe
            if message_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    await self.subscribe(connection, channel)
                    await self.send(
                        connection,
                        WebSocketMessage(
                            type=MessageType.SUBSCRIBED,
                            data={"channel": channel},
                        ),
                    )
                return

            if message_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    await self.unsubscribe(connection, channel)
                    await self.send(
                        connection,
                        WebSocketMessage(
                            type=MessageType.UNSUBSCRIBED,
                            data={"channel": channel},
                        ),
                    )
                return

            # Call registered handler
            if message_type in self._handlers:
                await self._handlers[message_type](connection, data.get("data", {}))
            else:
                logger.warning(f"No handler for message type: {message_type}")

        except json.JSONDecodeError:
            await self.send(
                connection,
                WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"message": "Invalid JSON"},
                ),
            )
        except Exception as e:
            logger.exception(f"Error handling WebSocket message: {e}")
            await self.send(
                connection,
                WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"message": "Internal error"},
                ),
            )

    async def _close_connection(self, connection: Connection, reason: str) -> None:
        """Close a connection with a reason."""
        try:
            await self.send(
                connection,
                WebSocketMessage(
                    type=MessageType.DISCONNECTED,
                    data={"reason": reason},
                ),
            )
            await connection.websocket.close()
        except Exception:
            pass
        finally:
            await self.disconnect(connection)

    async def _listen_redis(self) -> None:
        """Listen to Redis pub/sub for cross-instance messages."""
        while self._running:
            try:
                async with cache.subscribe("ws:broadcast") as pubsub:
                    async for message in pubsub.listen():
                        if not self._running:
                            break

                        if message["type"] != "message":
                            continue

                        try:
                            data = json.loads(message["data"])
                            await self._handle_redis_message(data)
                        except (json.JSONDecodeError, Exception) as e:
                            logger.error(f"Error processing Redis message: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis listener error: {e}")
                if self._running:
                    await asyncio.sleep(1)  # Reconnect delay

    async def _handle_redis_message(self, data: dict[str, Any]) -> None:
        """Handle a message received from Redis pub/sub."""
        action = data.get("action")

        if action == "broadcast_channel":
            channel = data.get("channel")
            message_data = data.get("message", {})
            if channel:
                await self.broadcast_to_channel(
                    channel,
                    WebSocketMessage(
                        type=message_data.get("type", "notification"),
                        data=message_data.get("data", {}),
                    ),
                )

        elif action == "broadcast_user":
            user_id = data.get("user_id")
            message_data = data.get("message", {})
            if user_id:
                await self.send_to_user(
                    user_id,
                    WebSocketMessage(
                        type=message_data.get("type", "notification"),
                        data=message_data.get("data", {}),
                    ),
                )

        elif action == "broadcast_all":
            message_data = data.get("message", {})
            await self.broadcast_all(
                WebSocketMessage(
                    type=message_data.get("type", "notification"),
                    data=message_data.get("data", {}),
                )
            )


# Global instance
ws_manager = WebSocketManager()


async def get_ws_manager() -> WebSocketManager:
    """Get the WebSocket manager instance."""
    return ws_manager


async def init_websocket() -> None:
    """Initialize WebSocket manager."""
    await ws_manager.start()
    logger.info("WebSocket manager initialized")


async def close_websocket() -> None:
    """Close WebSocket manager."""
    await ws_manager.stop()
    logger.info("WebSocket manager closed")


# ===========================================
# Utility functions for external use
# ===========================================


async def publish_to_channel(
    channel: str,
    message_type: str,
    data: dict[str, Any],
) -> None:
    """
    Publish a message to a WebSocket channel via Redis.

    This can be called from anywhere (including Celery workers)
    to send messages to WebSocket clients.
    """
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": channel,
            "message": {
                "type": message_type,
                "data": data,
            },
        },
    )


async def publish_to_user(
    user_id: str,
    message_type: str,
    data: dict[str, Any],
) -> None:
    """Publish a message to a specific user via Redis."""
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_user",
            "user_id": user_id,
            "message": {
                "type": message_type,
                "data": data,
            },
        },
    )


async def publish_task_update(
    task_id: str,
    status: str,
    progress: float,
    message: str | None = None,
    user_id: str | None = None,
) -> None:
    """
    Publish a task progress update.

    Publishes to both task-specific and user-specific channels.
    """
    data = {
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "message": message,
    }

    # Publish to task channel
    await publish_to_channel(f"task:{task_id}", MessageType.TASK_PROGRESS.value, data)

    # Also publish to user if known
    if user_id:
        await publish_to_user(user_id, MessageType.TASK_PROGRESS.value, data)


async def publish_rag_chunk(
    session_id: str,
    chunk: str,
    user_id: str,
) -> None:
    """Publish a RAG streaming chunk."""
    await publish_to_channel(
        f"rag:{session_id}",
        MessageType.RAG_CHUNK.value,
        {"chunk": chunk},
    )
