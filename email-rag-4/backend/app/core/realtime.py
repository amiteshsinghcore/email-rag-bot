"""
Real-time Updates Module

Provides utilities for publishing real-time updates through both
Redis pub/sub and WebSocket connections.
"""

from enum import Enum
from typing import Any

from loguru import logger

from app.core.cache import cache


class UpdateType(str, Enum):
    """Types of real-time updates."""

    # Task updates
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"

    # RAG updates
    RAG_CHUNK = "rag_chunk"
    RAG_COMPLETE = "rag_complete"
    RAG_ERROR = "rag_error"

    # Email updates
    EMAIL_INDEXED = "email_indexed"
    BATCH_INDEXED = "batch_indexed"

    # System notifications
    NOTIFICATION = "notification"
    SYSTEM_ALERT = "system_alert"


async def publish_task_started(
    task_id: str,
    user_id: str | None = None,
    task_type: str = "pst_processing",
    filename: str | None = None,
) -> None:
    """
    Publish task started notification.

    Args:
        task_id: The processing task ID
        user_id: User who owns the task
        task_type: Type of task (pst_processing, reindexing, etc.)
        filename: Original filename if applicable
    """
    data = {
        "task_id": task_id,
        "task_type": task_type,
        "status": "started",
        "progress": 0,
        "message": "Task started",
    }

    if filename:
        data["filename"] = filename

    # Publish to task channel
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"task:{task_id}",
            "message": {
                "type": UpdateType.TASK_STARTED.value,
                "data": data,
            },
        },
    )

    # Also publish to user if known
    if user_id:
        await cache.publish(
            "ws:broadcast",
            {
                "action": "broadcast_user",
                "user_id": user_id,
                "message": {
                    "type": UpdateType.TASK_STARTED.value,
                    "data": data,
                },
            },
        )

    logger.debug(f"Published task started: {task_id}")


async def publish_task_progress(
    task_id: str,
    progress: float,
    phase: str = "processing",
    message: str | None = None,
    user_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Publish task progress update.

    Args:
        task_id: The processing task ID
        progress: Progress percentage (0-100)
        phase: Current processing phase
        message: Human-readable status message
        user_id: User who owns the task
        details: Additional progress details (emails_processed, etc.)
    """
    data = {
        "task_id": task_id,
        "status": phase,
        "progress": min(100, max(0, progress)),
        "message": message or f"Processing ({phase})",
    }

    if details:
        data.update(details)

    # Publish to task channel
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"task:{task_id}",
            "message": {
                "type": UpdateType.TASK_PROGRESS.value,
                "data": data,
            },
        },
    )

    # Also update task status in cache for polling clients
    await cache.set_task_status(task_id, data)

    # Also publish to user if known
    if user_id:
        await cache.publish(
            "ws:broadcast",
            {
                "action": "broadcast_user",
                "user_id": user_id,
                "message": {
                    "type": UpdateType.TASK_PROGRESS.value,
                    "data": data,
                },
            },
        )


async def publish_task_completed(
    task_id: str,
    user_id: str | None = None,
    summary: dict[str, Any] | None = None,
) -> None:
    """
    Publish task completed notification.

    Args:
        task_id: The processing task ID
        user_id: User who owns the task
        summary: Summary of what was processed
    """
    data = {
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "message": "Processing complete",
    }

    if summary:
        data["summary"] = summary

    # Publish to task channel
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"task:{task_id}",
            "message": {
                "type": UpdateType.TASK_COMPLETED.value,
                "data": data,
            },
        },
    )

    # Update cache
    await cache.set_task_status(task_id, data)

    # Publish to user
    if user_id:
        await cache.publish(
            "ws:broadcast",
            {
                "action": "broadcast_user",
                "user_id": user_id,
                "message": {
                    "type": UpdateType.TASK_COMPLETED.value,
                    "data": data,
                },
            },
        )

    logger.info(f"Task completed: {task_id}")


async def publish_task_failed(
    task_id: str,
    error: str,
    user_id: str | None = None,
    error_type: str = "ProcessingError",
) -> None:
    """
    Publish task failure notification.

    Args:
        task_id: The processing task ID
        error: Error message
        user_id: User who owns the task
        error_type: Type of error for categorization
    """
    data = {
        "task_id": task_id,
        "status": "failed",
        "progress": 0,
        "message": error,
        "error_type": error_type,
    }

    # Publish to task channel
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"task:{task_id}",
            "message": {
                "type": UpdateType.TASK_FAILED.value,
                "data": data,
            },
        },
    )

    # Update cache
    await cache.set_task_status(task_id, data)

    # Publish to user
    if user_id:
        await cache.publish(
            "ws:broadcast",
            {
                "action": "broadcast_user",
                "user_id": user_id,
                "message": {
                    "type": UpdateType.TASK_FAILED.value,
                    "data": data,
                },
            },
        )

    logger.warning(f"Task failed: {task_id} - {error}")


async def publish_task_cancelled(
    task_id: str,
    user_id: str | None = None,
) -> None:
    """
    Publish task cancellation notification.

    Args:
        task_id: The processing task ID
        user_id: User who owns the task
    """
    data = {
        "task_id": task_id,
        "status": "cancelled",
        "progress": 0,
        "message": "Task cancelled by user",
    }

    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"task:{task_id}",
            "message": {
                "type": UpdateType.TASK_CANCELLED.value,
                "data": data,
            },
        },
    )

    await cache.set_task_status(task_id, data)

    if user_id:
        await cache.publish(
            "ws:broadcast",
            {
                "action": "broadcast_user",
                "user_id": user_id,
                "message": {
                    "type": UpdateType.TASK_CANCELLED.value,
                    "data": data,
                },
            },
        )

    logger.info(f"Task cancelled: {task_id}")


async def publish_rag_chunk(
    session_id: str,
    chunk: str,
    user_id: str,
) -> None:
    """
    Publish a RAG streaming response chunk.

    Args:
        session_id: The RAG session/conversation ID
        chunk: Text chunk from LLM
        user_id: User receiving the response
    """
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"rag:{session_id}",
            "message": {
                "type": UpdateType.RAG_CHUNK.value,
                "data": {"chunk": chunk},
            },
        },
    )


async def publish_rag_complete(
    session_id: str,
    user_id: str,
    sources: list[dict[str, Any]] | None = None,
    tokens_used: int = 0,
) -> None:
    """
    Publish RAG response completion.

    Args:
        session_id: The RAG session/conversation ID
        user_id: User receiving the response
        sources: Source documents used
        tokens_used: Total tokens consumed
    """
    data = {
        "complete": True,
        "tokens_used": tokens_used,
    }

    if sources:
        data["sources"] = sources

    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"rag:{session_id}",
            "message": {
                "type": UpdateType.RAG_COMPLETE.value,
                "data": data,
            },
        },
    )


async def publish_rag_error(
    session_id: str,
    user_id: str,
    error: str,
    error_type: str = "LLMError",
) -> None:
    """
    Publish RAG error notification.

    Args:
        session_id: The RAG session/conversation ID
        user_id: User receiving the response
        error: Error message
        error_type: Type of error
    """
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"rag:{session_id}",
            "message": {
                "type": UpdateType.RAG_ERROR.value,
                "data": {
                    "error": error,
                    "error_type": error_type,
                },
            },
        },
    )


async def publish_notification(
    user_id: str,
    title: str,
    message: str,
    notification_type: str = "info",
    data: dict[str, Any] | None = None,
) -> None:
    """
    Publish a user notification.

    Args:
        user_id: Target user ID
        title: Notification title
        message: Notification message
        notification_type: Type (info, success, warning, error)
        data: Additional data payload
    """
    notification_data = {
        "title": title,
        "message": message,
        "type": notification_type,
    }

    if data:
        notification_data["data"] = data

    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_user",
            "user_id": user_id,
            "message": {
                "type": UpdateType.NOTIFICATION.value,
                "data": notification_data,
            },
        },
    )


async def publish_system_alert(
    message: str,
    alert_type: str = "info",
    target_roles: list[str] | None = None,
) -> None:
    """
    Publish a system-wide alert.

    Args:
        message: Alert message
        alert_type: Alert type (info, warning, critical)
        target_roles: If specified, only send to users with these roles
    """
    alert_data = {
        "message": message,
        "type": alert_type,
        "target_roles": target_roles,
    }

    # Broadcast to all connected users
    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_all",
            "message": {
                "type": UpdateType.SYSTEM_ALERT.value,
                "data": alert_data,
            },
        },
    )

    logger.info(f"System alert published: {message}")


async def publish_batch_indexed(
    task_id: str,
    emails_count: int,
    attachments_count: int,
    chunks_count: int,
    user_id: str | None = None,
) -> None:
    """
    Publish batch indexing progress notification.

    Used during embedding phase to show indexing progress.
    """
    data = {
        "task_id": task_id,
        "emails_indexed": emails_count,
        "attachments_indexed": attachments_count,
        "chunks_created": chunks_count,
    }

    await cache.publish(
        "ws:broadcast",
        {
            "action": "broadcast_channel",
            "channel": f"task:{task_id}",
            "message": {
                "type": UpdateType.BATCH_INDEXED.value,
                "data": data,
            },
        },
    )

    if user_id:
        await cache.publish(
            "ws:broadcast",
            {
                "action": "broadcast_user",
                "user_id": user_id,
                "message": {
                    "type": UpdateType.BATCH_INDEXED.value,
                    "data": data,
                },
            },
        )
