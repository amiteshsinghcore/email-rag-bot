"""
Core Package

Contains core utilities, middleware, and infrastructure components.
"""

from app.core.cache import (
    CacheService,
    cache,
    close_cache,
    get_cache,
    init_cache,
)
from app.core.realtime import (
    UpdateType,
    publish_batch_indexed,
    publish_notification,
    publish_rag_chunk,
    publish_rag_complete,
    publish_rag_error,
    publish_system_alert,
    publish_task_cancelled,
    publish_task_completed,
    publish_task_failed,
    publish_task_progress,
    publish_task_started,
)
from app.core.security import (
    TokenPair,
    TokenPayload,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    get_password_hash,
    validate_password_strength,
    verify_access_token,
    verify_password,
    verify_refresh_token,
)
from app.core.websocket import (
    Connection,
    MessageType,
    WebSocketManager,
    WebSocketMessage,
    close_websocket,
    get_ws_manager,
    init_websocket,
    publish_to_channel,
    publish_to_user,
    ws_manager,
)

__all__ = [
    # Cache
    "CacheService",
    "cache",
    "get_cache",
    "init_cache",
    "close_cache",
    # Security
    "TokenPayload",
    "TokenPair",
    "verify_password",
    "get_password_hash",
    "create_access_token",
    "create_refresh_token",
    "create_token_pair",
    "decode_token",
    "verify_access_token",
    "verify_refresh_token",
    "validate_password_strength",
    # WebSocket
    "WebSocketManager",
    "WebSocketMessage",
    "MessageType",
    "Connection",
    "ws_manager",
    "get_ws_manager",
    "init_websocket",
    "close_websocket",
    "publish_to_channel",
    "publish_to_user",
    # Real-time Updates
    "UpdateType",
    "publish_task_started",
    "publish_task_progress",
    "publish_task_completed",
    "publish_task_failed",
    "publish_task_cancelled",
    "publish_rag_chunk",
    "publish_rag_complete",
    "publish_rag_error",
    "publish_notification",
    "publish_system_alert",
    "publish_batch_indexed",
]
