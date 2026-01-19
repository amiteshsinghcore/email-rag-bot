"""
Email Processing Tasks

Celery tasks for processing PST files and extracting emails.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import redis.asyncio as aioredis
from celery import current_task
from loguru import logger
from sqlalchemy import select

from app.config import settings
from app.db.models.attachment import Attachment
from app.db.models.email import Email
from app.db.models.processing_task import ProcessingTask, TaskStatus
from app.db.session import get_worker_db_context
from app.services.attachment_processor import (
    AttachmentProcessor,
    UnsupportedFormatError,
)


def sanitize_text_for_db(text: str | None) -> str | None:
    """
    Sanitize text for PostgreSQL storage.
    Removes null bytes and other invalid characters.
    """
    if not text:
        return text

    import re
    # Remove null bytes (PostgreSQL doesn't accept \x00)
    text = text.replace('\x00', '')
    # Remove other control characters except newlines, tabs, carriage returns
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    return text


from app.services.embedding_service import embedding_service
from app.services.pst_processor import PSTProcessor, PSTProcessorError
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
        emails_failed: int | None = None,
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
            if emails_failed is not None:
                data["emails_failed"] = emails_failed
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
        # Log the error for debugging
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
    name="app.workers.email_tasks.process_pst_file",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def process_pst_file(self, task_id: str) -> dict:
    """
    Process a PST file and extract all emails.

    This is the main entry point for PST processing.

    Args:
        task_id: UUID of the ProcessingTask

    Returns:
        Processing result summary
    """
    logger.info(f"Starting PST processing for task {task_id}")

    try:
        result = run_async(_process_pst_file_async(self, task_id))

        # Check if async function returned a retry request
        if isinstance(result, dict) and result.get("should_retry"):
            exc = result.get("exception")
            if exc and self.request.retries < self.max_retries:
                logger.info(f"Retrying task {task_id} due to error: {exc}")
                raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

        return result
    except Exception as e:
        logger.exception(f"Task failed with exception: {e}")
        raise


async def _process_pst_file_async(task, task_id: str) -> dict:
    """Async implementation of PST processing."""
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
                # Update task status
                processing_task.status = TaskStatus.PARSING
                processing_task.celery_task_id = task.request.id
                processing_task.started_at = datetime.now(timezone.utc)
                await db.commit()

                # Publish status update
                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="parsing",
                    progress=5.0,
                    message="Opening PST file...",
                    current_phase="parsing",
                )

                # Process the PST file
                pst_path = Path(processing_task.file_path)

                if not pst_path.exists():
                    raise PSTProcessorError(f"PST file not found: {pst_path}")

                # Initialize processor
                processor = PSTProcessor(pst_path)
                processor.open()

                try:
                    # Count emails for progress tracking
                    processing_task.current_phase = "counting"
                    await db.commit()

                    total_emails = processor.count_emails()
                    processing_task.emails_total = total_emails

                    await worker_cache.publish_task_update(
                        task_id=task_id,
                        status="parsing",
                        progress=10.0,
                        message=f"Found {total_emails} emails to process",
                        emails_total=total_emails,
                        current_phase="counting",
                    )

                    # Process emails
                    processing_task.status = TaskStatus.EXTRACTING
                    processing_task.current_phase = "extracting"
                    await db.commit()

                    attachment_processor = AttachmentProcessor()
                    emails_processed = 0
                    emails_failed = 0

                    for extracted_email in processor.extract_emails():
                        try:
                            # Convert references list to string (space-separated)
                            references_str = " ".join(extracted_email.references) if extracted_email.references else None

                            # Serialize headers dict to JSON string
                            import json
                            headers_str = json.dumps(extracted_email.headers) if extracted_email.headers else None

                            # Sanitize text fields for PostgreSQL (remove null bytes)
                            sanitized_subject = sanitize_text_for_db(extracted_email.subject)
                            sanitized_body_text = sanitize_text_for_db(extracted_email.body_text)
                            sanitized_body_html = sanitize_text_for_db(extracted_email.body_html)
                            sanitized_sender_name = sanitize_text_for_db(extracted_email.sender_name)
                            sanitized_folder = sanitize_text_for_db(extracted_email.folder_path)

                            # Create email record
                            email = Email(
                                pst_file_id=processing_task.id,
                                message_id=extracted_email.message_id,
                                internet_message_id=extracted_email.internet_message_id,
                                thread_id=extracted_email.thread_id,
                                in_reply_to=extracted_email.in_reply_to,
                                references=references_str,
                                sender_email=extracted_email.sender_email,
                                sender_name=sanitized_sender_name,
                                to_recipients=extracted_email.to_recipients,
                                cc_recipients=extracted_email.cc_recipients,
                                bcc_recipients=extracted_email.bcc_recipients,
                                subject=sanitized_subject,
                                body_text=sanitized_body_text,
                                body_html=sanitized_body_html,
                                sent_date=extracted_email.sent_date,
                                received_date=extracted_email.received_date,
                                importance=extracted_email.importance,
                                is_read=extracted_email.is_read,
                                has_attachments=extracted_email.has_attachments,
                                folder_path=sanitized_folder,
                                headers=headers_str,
                                sha256_hash=extracted_email.sha256_hash,
                            )

                            db.add(email)
                            await db.flush()  # Get the email ID

                            # Process attachments
                            for ext_attachment in extracted_email.attachments:
                                # Try to extract text
                                extracted_text = None
                                is_extracted = False

                                # Pass content for magic byte detection since filenames may be generic
                                if attachment_processor.can_process(
                                    ext_attachment.filename,
                                    ext_attachment.content_type,
                                    ext_attachment.content,  # Pass content for magic byte detection
                                ):
                                    try:
                                        extracted_text = attachment_processor.extract_text_from_attachment(
                                            ext_attachment.content,
                                            ext_attachment.filename,
                                            ext_attachment.content_type,
                                        )
                                        is_extracted = True
                                    except UnsupportedFormatError:
                                        pass
                                    except Exception as e:
                                        logger.warning(
                                            f"Failed to extract text from {ext_attachment.filename}: {e}"
                                        )

                                # Save attachment to storage
                                storage_path = await _save_attachment(
                                    processing_task.id,
                                    str(email.id),
                                    ext_attachment.filename,
                                    ext_attachment.content,
                                )

                                # Create attachment record
                                attachment = Attachment(
                                    email_id=email.id,
                                    filename=ext_attachment.filename,
                                    content_type=ext_attachment.content_type,
                                    size_bytes=ext_attachment.size_bytes,
                                    md5_hash=ext_attachment.md5_hash,
                                    sha256_hash=ext_attachment.sha256_hash,
                                    storage_path=storage_path,
                                    extracted_text=extracted_text,
                                    is_extracted=is_extracted,
                                )
                                db.add(attachment)

                            emails_processed += 1

                            # Update progress periodically
                            if emails_processed % 100 == 0:
                                processing_task.emails_processed = emails_processed
                                await db.commit()

                                progress = 10 + (emails_processed / total_emails * 50)
                                await worker_cache.publish_task_update(
                                    task_id=task_id,
                                    status="extracting",
                                    progress=progress,
                                    message=f"Processed {emails_processed}/{total_emails} emails",
                                    emails_processed=emails_processed,
                                    emails_total=total_emails,
                                    emails_failed=emails_failed,
                                    current_phase="extracting",
                                )

                        except Exception as e:
                            logger.error(f"Error processing email: {e}")
                            emails_failed += 1
                            # Just continue to next email - will commit at intervals
                            continue

                    # Commit all emails
                    await db.commit()

                    processing_task.emails_processed = emails_processed
                    processing_task.emails_failed = emails_failed

                    logger.info(
                        f"Extracted {emails_processed} emails "
                        f"({emails_failed} failed) from {pst_path}"
                    )

                finally:
                    processor.close()

                # Start embedding phase
                processing_task.status = TaskStatus.EMBEDDING
                processing_task.current_phase = "embedding"
                await db.commit()

                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="embedding",
                    progress=60.0,
                    message="Generating embeddings...",
                    emails_processed=emails_processed,
                    emails_total=total_emails,
                    emails_failed=emails_failed,
                    current_phase="embedding",
                )

                # Trigger embedding task
                from app.workers.indexing_tasks import embed_emails_for_task

                embed_emails_for_task.delay(task_id)

                return {
                    "status": "embedding_started",
                    "emails_processed": emails_processed,
                    "emails_failed": emails_failed,
                }

            except PSTProcessorError as e:
                logger.error(f"PST processing error: {e}")
                processing_task.status = TaskStatus.FAILED
                processing_task.error_message = str(e)
                await db.commit()

                await worker_cache.publish_task_update(
                    task_id=task_id,
                    status="failed",
                    progress=0,
                    message=str(e),
                )

                return {"error": str(e)}

            except Exception as e:
                logger.exception(f"Unexpected error processing PST: {e}")
                processing_task.status = TaskStatus.FAILED
                processing_task.error_message = f"Unexpected error: {e}"
                await db.commit()

                try:
                    await worker_cache.publish_task_update(
                        task_id=task_id,
                        status="failed",
                        progress=0,
                        message=f"Unexpected error: {e}",
                    )
                except Exception as cache_error:
                    logger.warning(f"Failed to publish cache update: {cache_error}")

                return {"error": str(e), "should_retry": True, "exception": e}


async def _save_attachment(
    task_id: str,
    email_id: str,
    filename: str,
    content: bytes,
) -> str:
    """Save attachment to storage and return path."""
    # Create directory structure
    storage_dir = Path(settings.upload_dir) / "attachments" / task_id / email_id
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_filename = "".join(
        c for c in filename if c.isalnum() or c in "._-"
    )[:255]

    if not safe_filename:
        safe_filename = "attachment"

    # Handle duplicate filenames
    file_path = storage_dir / safe_filename
    counter = 1
    while file_path.exists():
        name, ext = safe_filename.rsplit(".", 1) if "." in safe_filename else (safe_filename, "")
        file_path = storage_dir / f"{name}_{counter}.{ext}" if ext else storage_dir / f"{name}_{counter}"
        counter += 1

    # Write file
    file_path.write_bytes(content)

    return str(file_path)


@celery_app.task(
    name="app.workers.email_tasks.cancel_processing",
)
def cancel_processing(task_id: str) -> dict:
    """Cancel a running PST processing task."""
    return run_async(_cancel_processing_async(task_id))


async def _cancel_processing_async(task_id: str) -> dict:
    """Async implementation of task cancellation."""
    async with get_worker_db_context() as db:
        result = await db.execute(
            select(ProcessingTask).where(ProcessingTask.id == task_id)
        )
        processing_task = result.scalar_one_or_none()

        if not processing_task:
            return {"error": "Task not found"}

        if not processing_task.is_active:
            return {"error": "Task is not active"}

        # Revoke the Celery task
        if processing_task.celery_task_id:
            celery_app.control.revoke(
                processing_task.celery_task_id,
                terminate=True,
            )

        processing_task.status = TaskStatus.CANCELLED
        await db.commit()

        await worker_cache.publish_task_update(
            task_id=task_id,
            status="cancelled",
            progress=processing_task.progress_percent,
            message="Task cancelled by user",
        )

        return {"status": "cancelled"}
