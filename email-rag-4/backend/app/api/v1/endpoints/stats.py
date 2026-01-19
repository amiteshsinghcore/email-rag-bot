"""
Stats API Endpoints

Dashboard statistics and metrics.
"""

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.db.models.attachment import Attachment
from app.db.models.email import Email
from app.db.models.processing_task import ProcessingTask, TaskStatus

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get dashboard statistics."""
    # Count total emails
    email_count_result = await db.execute(select(func.count(Email.id)))
    total_emails = email_count_result.scalar() or 0

    # Count emails with attachments
    emails_with_attachments_result = await db.execute(
        select(func.count(Email.id)).where(Email.has_attachments == True)
    )
    emails_with_attachments = emails_with_attachments_result.scalar() or 0

    # Count total attachments
    attachment_count_result = await db.execute(select(func.count(Attachment.id)))
    total_attachments = attachment_count_result.scalar() or 0

    # Count PST files
    pst_count_result = await db.execute(select(func.count(ProcessingTask.id)))
    total_pst_files = pst_count_result.scalar() or 0

    # Count completed tasks
    completed_result = await db.execute(
        select(func.count(ProcessingTask.id)).where(
            ProcessingTask.status == TaskStatus.COMPLETED
        )
    )
    completed_tasks = completed_result.scalar() or 0

    # Count in-progress tasks (parsing, extracting, embedding, etc.)
    in_progress_statuses = [
        TaskStatus.UPLOADING,
        TaskStatus.VALIDATING,
        TaskStatus.PARSING,
        TaskStatus.EXTRACTING,
        TaskStatus.EMBEDDING,
        TaskStatus.INDEXING,
    ]
    processing_result = await db.execute(
        select(func.count(ProcessingTask.id)).where(
            ProcessingTask.status.in_(in_progress_statuses)
        )
    )
    processing_tasks = processing_result.scalar() or 0

    # Calculate storage used (sum of all PST file sizes)
    storage_result = await db.execute(
        select(func.sum(ProcessingTask.file_size_bytes))
    )
    storage_used = storage_result.scalar() or 0

    return {
        "total_emails": total_emails,
        "emails_with_attachments": emails_with_attachments,
        "total_pst_files": total_pst_files,
        "completed_tasks": completed_tasks,
        "processing_tasks": processing_tasks,
        "total_attachments": total_attachments,
        "storage_used": storage_used,
    }
