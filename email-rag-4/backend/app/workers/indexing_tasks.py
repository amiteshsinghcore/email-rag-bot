"""
Indexing Tasks

Celery tasks for generating embeddings and indexing email content.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as aioredis
from celery import current_task
from loguru import logger
from sqlalchemy import select

from app.config import settings
from app.db.models.attachment import Attachment
from app.db.models.email import Email
from app.db.models.processing_task import ProcessingTask, TaskStatus
from app.db.session import get_worker_db_context
from app.services.embedding_service import embedding_service
from app.workers.celery_app import celery_app


class WorkerCacheService:
    """
    Worker-specific cache service that creates fresh connections per task.

    This avoids event loop issues by not reusing connections across tasks.
    """

    def __init__(self):
        self._client = None

    async def connect(self):
        """Create a fresh Redis connection for this worker task."""
        self._client = await aioredis.from_url(
            settings.redis_connection_url,
            decode_responses=True,
        )
        return self

    async def close(self):
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None

    async def publish_task_update(
        self,
        task_id: str,
        status: str,
        progress: float,
        message: str | None = None,
        emails_processed: int | None = None,
        emails_total: int | None = None,
        current_phase: str | None = None,
    ) -> None:
        """Publish a task progress update via ws:broadcast channel."""
        if not self._client:
            logger.warning("Cache not connected, skipping publish")
            return

        import json
        try:
            # Build data payload with all available info
            data = {
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "message": message,
            }

            # Add optional fields if provided
            if emails_processed is not None:
                data["emails_processed"] = emails_processed
            if emails_total is not None:
                data["emails_total"] = emails_total
            if current_phase is not None:
                data["current_phase"] = current_phase

            # Publish to ws:broadcast channel with the format expected by WebSocket manager
            await self._client.publish(
                "ws:broadcast",
                json.dumps({
                    "action": "broadcast_channel",
                    "channel": f"task:{task_id}",
                    "message": {
                        "type": "task_progress",
                        "data": data,
                    },
                }),
            )
        except Exception as e:
            logger.warning(f"Failed to publish task update: {e}")


@asynccontextmanager
async def get_worker_cache():
    """Context manager for worker-specific cache connections."""
    cache = WorkerCacheService()
    try:
        await cache.connect()
        yield cache
    finally:
        await cache.close()


def run_async(coro):
    """
    Helper to run async code in sync context with proper cleanup.

    Creates a new event loop for each task execution to ensure
    isolation and prevent cross-task event loop contamination.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"Async task failed: {e}")
        raise
    finally:
        try:
            # Cancel any pending tasks
            pending = asyncio.all_tasks(loop)
            for pending_task in pending:
                pending_task.cancel()

            # Wait for cancellation with timeout
            if pending:
                loop.run_until_complete(
                    asyncio.wait(pending, timeout=5.0)
                )

            # Shut down async generators
            loop.run_until_complete(loop.shutdown_asyncgens())

            # Shut down default executor
            loop.run_until_complete(loop.shutdown_default_executor())
        except Exception as cleanup_error:
            logger.warning(f"Event loop cleanup warning: {cleanup_error}")
        finally:
            loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.indexing_tasks.embed_emails_for_task",
    max_retries=3,
    default_retry_delay=60,
)
def embed_emails_for_task(self, task_id: str) -> dict:
    """
    Generate embeddings for all emails in a processing task.

    Args:
        task_id: UUID of the ProcessingTask

    Returns:
        Embedding result summary
    """
    logger.info(f"Starting embedding generation for task {task_id}")

    return run_async(_embed_emails_async(self, task_id))


async def _embed_emails_async(task, task_id: str) -> dict:
    """Async implementation of email embedding."""
    async with get_worker_cache() as worker_cache:
        async with get_worker_db_context() as db:
            # Get the processing task
            result = await db.execute(
                select(ProcessingTask).where(ProcessingTask.id == task_id)
            )
            processing_task = result.scalar_one_or_none()

            if not processing_task:
                logger.error(f"Processing task not found: {task_id}")
                return {"error": "Task not found"}

            try:
                # Update status
                processing_task.status = TaskStatus.EMBEDDING
                processing_task.current_phase = "embedding_emails"
                await db.commit()

                # Get all unembedded emails for this task
                result = await db.execute(
                    select(Email)
                    .where(
                        Email.pst_file_id == processing_task.id,
                        Email.is_embedded.is_(False),
                    )
                    .order_by(Email.created_at)
                )
                emails = list(result.scalars().all())

                total_emails = len(emails)
                emails_embedded = 0
                total_chunks = 0

                logger.info(f"Embedding {total_emails} emails for task {task_id}")

                # Process emails in batches
                batch_size = 50

                for i in range(0, total_emails, batch_size):
                    batch = emails[i : i + batch_size]

                    for email in batch:
                        try:
                            # Embed email content
                            # Store date as Unix timestamp for ChromaDB numeric filtering
                            date_timestamp = email.sent_date.timestamp() if email.sent_date else None

                            chunks_created = await embedding_service.embed_and_store_email(
                                email_id=str(email.id),
                                subject=email.subject or "",
                                body=email.body_text or "",
                                sender=email.sender_email or "",
                                recipients=email.to_recipients or [],
                                metadata={
                                    "pst_file_id": str(processing_task.id),
                                    "date": date_timestamp,  # Unix timestamp for ChromaDB filtering
                                    "sent_date": email.sent_date.isoformat() if email.sent_date else None,  # Human-readable
                                    "folder_path": email.folder_path,
                                },
                            )

                            # Mark email as embedded
                            email.is_embedded = True
                            email.embedding_id = str(email.id)
                            total_chunks += chunks_created
                            emails_embedded += 1

                        except Exception as e:
                            logger.error(f"Error embedding email {email.id}: {e}")
                            continue

                    # Commit batch and update progress
                    await db.commit()

                    progress = 60 + (emails_embedded / total_emails * 30) if total_emails > 0 else 90
                    await worker_cache.publish_task_update(
                        task_id=task_id,
                        status="embedding",
                        progress=progress,
                        message=f"Embedded {emails_embedded}/{total_emails} emails",
                        emails_processed=emails_embedded,
                        emails_total=total_emails,
                        current_phase="embedding_emails",
                    )

                # Now embed attachments
                processing_task.current_phase = "embedding_attachments"
                await db.commit()

                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="embedding",
                    progress=90.0,
                    message="Embedding attachment content...",
                    current_phase="embedding_attachments",
                )

                # Get all unembedded attachments with extracted text
                result = await db.execute(
                    select(Attachment)
                    .join(Email)
                    .where(
                        Email.pst_file_id == processing_task.id,
                        Attachment.is_extracted.is_(True),
                        Attachment.is_embedded.is_(False),
                        Attachment.extracted_text.isnot(None),
                    )
                )
                attachments = list(result.scalars().all())

                total_attachments = len(attachments)
                attachments_embedded = 0

                for attachment in attachments:
                    try:
                        chunks_created = await embedding_service.embed_and_store_attachment(
                            attachment_id=str(attachment.id),
                            email_id=str(attachment.email_id),
                            filename=attachment.filename,
                            content=attachment.extracted_text,
                            metadata={
                                "pst_file_id": str(processing_task.id),
                                "content_type": attachment.content_type,
                            },
                        )

                        attachment.is_embedded = True
                        total_chunks += chunks_created
                        attachments_embedded += 1

                    except Exception as e:
                        logger.error(f"Error embedding attachment {attachment.id}: {e}")
                        continue

                await db.commit()

                # Start indexing phase
                processing_task.status = TaskStatus.INDEXING
                processing_task.current_phase = "finalizing"
                await db.commit()

                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="indexing",
                    progress=95.0,
                    message="Finalizing index...",
                    current_phase="finalizing",
                )

                # Mark task as complete
                processing_task.status = TaskStatus.COMPLETED
                processing_task.current_phase = "completed"
                processing_task.completed_at = datetime.now(timezone.utc)
                processing_task.progress_percent = 100.0
                await db.commit()

                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="completed",
                    progress=100.0,
                    message=f"Completed: {emails_embedded} emails, {attachments_embedded} attachments indexed",
                    emails_processed=emails_embedded,
                    emails_total=total_emails,
                    current_phase="completed",
                )

                logger.info(
                    f"Embedding complete for task {task_id}: "
                    f"{emails_embedded} emails, {attachments_embedded} attachments, "
                    f"{total_chunks} total chunks"
                )

                return {
                    "status": "completed",
                    "emails_embedded": emails_embedded,
                    "attachments_embedded": attachments_embedded,
                    "total_chunks": total_chunks,
                }

            except Exception as e:
                logger.exception(f"Error during embedding: {e}")
                processing_task.status = TaskStatus.FAILED
                processing_task.error_message = f"Embedding error: {e}"
                await db.commit()

                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="failed",
                    progress=0,
                    message=f"Embedding error: {e}",
                )

                raise task.retry(exc=e)


@celery_app.task(
    name="app.workers.indexing_tasks.reindex_email",
)
def reindex_email(email_id: str) -> dict:
    """Re-index a single email (e.g., after content update)."""
    return run_async(_reindex_email_async(email_id))


async def _reindex_email_async(email_id: str) -> dict:
    """Async implementation of email re-indexing."""
    async with get_worker_db_context() as db:
        result = await db.execute(select(Email).where(Email.id == email_id))
        email = result.scalar_one_or_none()

        if not email:
            return {"error": "Email not found"}

        try:
            # Delete existing embeddings
            from app.services.vector_store import vector_store

            vector_store.delete_by_email_id(str(email.id))

            # Re-embed
            date_timestamp = email.sent_date.timestamp() if email.sent_date else None

            chunks_created = await embedding_service.embed_and_store_email(
                email_id=str(email.id),
                subject=email.subject or "",
                body=email.body_text or "",
                sender=email.sender_email or "",
                recipients=email.to_recipients or [],
                metadata={
                    "pst_file_id": str(email.pst_file_id),
                    "date": date_timestamp,  # Unix timestamp for ChromaDB filtering
                    "sent_date": email.sent_date.isoformat() if email.sent_date else None,
                    "folder_path": email.folder_path,
                },
            )

            email.is_embedded = True
            await db.commit()

            return {
                "status": "success",
                "chunks_created": chunks_created,
            }

        except Exception as e:
            logger.error(f"Error re-indexing email {email_id}: {e}")
            return {"error": str(e)}


@celery_app.task(
    name="app.workers.indexing_tasks.delete_embeddings_for_task",
)
def delete_embeddings_for_task(task_id: str) -> dict:
    """Delete all embeddings for a processing task."""
    from app.services.vector_store import vector_store

    try:
        vector_store.delete_by_pst_file(task_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error deleting embeddings for task {task_id}: {e}")
        return {"error": str(e)}
