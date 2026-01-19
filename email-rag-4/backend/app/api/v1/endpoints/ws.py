"""
WebSocket API Endpoint

Real-time communication endpoint for task progress, RAG streaming, and notifications.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from loguru import logger

from app.core.websocket import MessageType, WebSocketMessage, get_ws_manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket connection endpoint.

    Authentication:
        Token can be passed as:
        - Query parameter: ws://host/api/v1/ws?token=xxx
        - Header: Authorization: Bearer xxx

    Message Format (incoming):
        {
            "type": "subscribe|unsubscribe|ping|...",
            "channel": "task:123",  // for subscribe/unsubscribe
            "data": {}  // for other message types
        }

    Message Format (outgoing):
        {
            "type": "connected|task_progress|rag_chunk|...",
            "data": {...},
            "channel": "task:123",  // if channel-specific
            "timestamp": "2024-01-01T00:00:00Z"
        }

    Channels:
        - task:{task_id} - Task progress updates
        - rag:{session_id} - RAG response streaming
        - user:{user_id} - User-specific notifications (auto-subscribed)

    Message Types (incoming):
        - ping: Keep-alive ping (responds with pong)
        - subscribe: Subscribe to a channel
        - unsubscribe: Unsubscribe from a channel

    Message Types (outgoing):
        - connected: Initial connection confirmation
        - disconnected: Connection closed
        - error: Error message
        - pong: Response to ping
        - subscribed: Subscription confirmed
        - unsubscribed: Unsubscription confirmed
        - task_started: Task has started
        - task_progress: Task progress update
        - task_completed: Task completed successfully
        - task_failed: Task failed
        - rag_chunk: Streaming RAG response chunk
        - rag_complete: RAG response complete
        - rag_error: RAG error occurred
        - notification: General notification
    """
    ws_manager = await get_ws_manager()

    # Authenticate the connection
    auth_result = await ws_manager.authenticate(websocket)

    if not auth_result:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication required",
        )
        return

    user_id, user_role = auth_result

    # Accept and register connection
    connection = await ws_manager.connect(websocket, user_id, user_role)

    try:
        # Message handling loop
        while True:
            try:
                raw_message = await websocket.receive_text()
                await ws_manager.handle_message(connection, raw_message)

            except WebSocketDisconnect:
                break

    except Exception as e:
        logger.exception(f"WebSocket error for user {user_id}: {e}")
        try:
            await ws_manager.send(
                connection,
                WebSocketMessage(
                    type=MessageType.ERROR,
                    data={"message": "Connection error"},
                ),
            )
        except Exception:
            pass

    finally:
        await ws_manager.disconnect(connection)


@router.get(
    "/ws/info",
    summary="WebSocket info",
    description="Get WebSocket connection information and statistics.",
)
async def websocket_info() -> dict:
    """
    Get WebSocket server information.

    Returns connection statistics and available channels.
    """
    ws_manager = await get_ws_manager()

    return {
        "total_connections": ws_manager.connection_count,
        "unique_users": ws_manager.user_count,
        "status": "running",
        "supported_message_types": [mt.value for mt in MessageType],
        "channel_patterns": [
            "task:{task_id} - Task progress updates",
            "rag:{session_id} - RAG response streaming",
            "user:{user_id} - User-specific notifications",
        ],
    }
