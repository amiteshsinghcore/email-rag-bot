"""
Upload Endpoints

Handles PST file uploads and processing task management.
"""

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from loguru import logger
from sqlalchemy import delete, func, select

from app.api.deps import ActiveUser, AdminUser, DbSession
from app.config import settings
from app.db.models.attachment import Attachment
from app.db.models.email import Email
from app.db.models.processing_task import ProcessingTask, TaskStatus
from app.schemas.auth import MessageResponse
from app.schemas.upload import (
    CancelTaskResponse,
    DeleteTaskResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskStatusResponse,
    UploadResponse,
    ChunkUploadInitRequest,
    ChunkUploadInitResponse,
)
from app.workers.email_tasks import cancel_processing, process_pst_file
from app.workers.indexing_tasks import delete_embeddings_for_task
import aiofiles
import os

router = APIRouter(prefix="/upload", tags=["Upload"])


# Maximum file size (10GB)
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024


@router.get("/files")
async def get_pst_files(
    current_user: ActiveUser,
    db: DbSession,
) -> list[dict]:
    """Get all PST files (processing tasks) for the current user."""
    result = await db.execute(
        select(ProcessingTask)
        .where(ProcessingTask.user_id == current_user.id)
        .order_by(ProcessingTask.created_at.desc())
    )
    tasks = result.scalars().all()

    # Build response with attachment counts
    response = []
    for t in tasks:
        # Count attachments for this task's emails
        attachment_count_result = await db.execute(
            select(func.count(Attachment.id))
            .select_from(Attachment)
            .join(Email, Attachment.email_id == Email.id)
            .where(Email.pst_file_id == t.id)
        )
        attachment_count = attachment_count_result.scalar() or 0

        response.append({
            "id": str(t.id),
            "filename": t.original_filename,
            "original_filename": t.original_filename,
            "file_size": t.file_size_bytes,
            "status": t.status.value if hasattr(t.status, 'value') else str(t.status),
            "progress": t.progress_percent,
            "current_phase": t.current_phase,
            "email_count": t.emails_processed or 0,
            "emails_total": t.emails_total or 0,
            "attachment_count": attachment_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "processed_at": t.completed_at.isoformat() if t.completed_at else None,
            "error_message": t.error_message,
        })

    return response


@router.get("/files/{file_id}")
async def get_pst_file(
    file_id: UUID,
    current_user: ActiveUser,
    db: DbSession,
) -> dict:
    """Get a specific PST file by ID."""
    result = await db.execute(
        select(ProcessingTask).where(
            ProcessingTask.id == file_id,
            ProcessingTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    return {
        "id": str(task.id),
        "filename": task.original_filename,
        "file_size": task.file_size_bytes,
        "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
        "progress": task.progress_percent,
        "emails_count": task.emails_processed or 0,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "error": task.error_message,
    }


@router.delete("/files/{file_id}")
async def delete_pst_file(
    file_id: UUID,
    current_user: ActiveUser,
    db: DbSession,
) -> dict:
    """Delete a PST file and associated data."""
    result = await db.execute(
        select(ProcessingTask).where(
            ProcessingTask.id == file_id,
            ProcessingTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found",
        )

    if task.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete active task. Cancel it first.",
        )

    # Delete emails and task
    await db.execute(delete(Email).where(Email.pst_file_id == file_id))
    await db.execute(delete(ProcessingTask).where(ProcessingTask.id == file_id))
    await db.commit()

    return {"message": "File deleted successfully"}


@router.post("/chunk/init", response_model=ChunkUploadInitResponse)
async def init_chunk_upload(
    request: ChunkUploadInitRequest,
    current_user: ActiveUser,
) -> ChunkUploadInitResponse:
    """Initialize a chunked upload session."""
    import uuid
    upload_id = str(uuid.uuid4())
    
    # Create temp directory for chunks
    temp_dir = Path(settings.upload_dir) / "temp" / upload_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    return ChunkUploadInitResponse(
        upload_id=upload_id,
        chunk_size=95 * 1024 * 1024  # 95MB
    )


@router.post("/chunk/{upload_id}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int = Query(..., ge=0),
    file: UploadFile = File(...),
    current_user: ActiveUser = None, # Optional auth check if needed, but path is unique
) -> dict:
    """Upload a single file chunk."""
    temp_dir = Path(settings.upload_dir) / "temp" / upload_id
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")
        
    chunk_path = temp_dir / f"{chunk_index}"
    
    try:
        async with aiofiles.open(chunk_path, 'wb') as f:
            while content := await file.read(8192):
                await f.write(content)
                
        return {"message": "Chunk uploaded", "index": chunk_index}
    except Exception as e:
        logger.error(f"Chunk upload error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save chunk")


@router.post("/chunk/{upload_id}/complete", response_model=UploadResponse)
async def complete_chunk_upload(
    upload_id: str,
    filename: str,
    current_user: ActiveUser,
    db: DbSession,
) -> UploadResponse:
    """Complete a chunked upload by assembling parts."""
    temp_dir = Path(settings.upload_dir) / "temp" / upload_id
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Upload session not found")

    try:
        # Verify all chunks exist (simple check - should be more robust in prod)
        chunks = sorted([int(f.name) for f in temp_dir.iterdir() if f.name.isdigit()])
        if not chunks:
             raise HTTPException(status_code=400, detail="No chunks found")
             
        # Create final file path
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")[:100]
        unique_filename = f"{current_user.id}_{timestamp}_{safe_filename}"
        final_path = Path(settings.upload_dir) / unique_filename
        
        # Assemble file
        file_size = 0
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        
        with open(final_path, 'wb') as outfile:
            for i in chunks:
                chunk_path = temp_dir / str(i)
                with open(chunk_path, 'rb') as infile:
                    while True:
                        data = infile.read(81920) # 80KB buffer
                        if not data:
                            break
                        outfile.write(data)
                        sha256.update(data)
                        md5.update(data)
                        file_size += len(data)

        # Cleanup chunks
        import shutil
        shutil.rmtree(temp_dir)
        
        sha256_hash = sha256.hexdigest()
        md5_hash = md5.hexdigest()

        # Check for duplicates
        result = await db.execute(
            select(ProcessingTask).where(
                ProcessingTask.sha256_hash == sha256_hash,
                ProcessingTask.status != TaskStatus.FAILED,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            final_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This file has already been processed (task: {existing.id})",
            )

        # Create task
        task = ProcessingTask(
            user_id=current_user.id,
            original_filename=filename,
            file_path=str(final_path),
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            md5_hash=md5_hash,
            status=TaskStatus.PENDING,
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        process_pst_file.delay(str(task.id))

        return UploadResponse(
            task_id=task.id,
            filename=filename,
            file_size=file_size,
            message="Upload successful, processing started",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assembly error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to assemble file: {str(e)}")


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_pst_file(
    current_user: ActiveUser,
    db: DbSession,
    file: UploadFile = File(..., description="PST file to upload"),
) -> UploadResponse:
    """
    Upload a PST file for processing.

    - Validates file type and size
    - Saves file to storage
    - Creates processing task
    - Starts background processing
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    if not file.filename.lower().endswith(".pst"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PST files are allowed",
        )

    # Check content type (optional, as PST files don't have standard MIME type)
    # PST files might be: application/vnd.ms-outlook-pst, application/octet-stream

    # Create upload directory
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_filename = "".join(
        c for c in file.filename if c.isalnum() or c in "._-"
    )[:100]
    unique_filename = f"{current_user.id}_{timestamp}_{safe_filename}"
    file_path = upload_dir / unique_filename

    try:
        # Stream file to disk while calculating hashes
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()
        file_size = 0

        with open(file_path, "wb") as f:
            while chunk := await file.read(8192):
                # Check size limit
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    f.close()
                    file_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024**3):.1f} GB",
                    )

                f.write(chunk)
                sha256.update(chunk)
                md5.update(chunk)

        sha256_hash = sha256.hexdigest()
        md5_hash = md5.hexdigest()

        logger.info(f"Uploaded file: {file.filename} ({file_size} bytes)")

        # Check for duplicate file
        result = await db.execute(
            select(ProcessingTask).where(
                ProcessingTask.sha256_hash == sha256_hash,
                ProcessingTask.status != TaskStatus.FAILED,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Delete uploaded file
            file_path.unlink()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This file has already been processed (task: {existing.id})",
            )

        # Create processing task
        task = ProcessingTask(
            user_id=current_user.id,
            original_filename=file.filename,
            file_path=str(file_path),
            file_size_bytes=file_size,
            sha256_hash=sha256_hash,
            md5_hash=md5_hash,
            status=TaskStatus.PENDING,
        )

        db.add(task)
        await db.commit()
        await db.refresh(task)

        logger.info(f"Created processing task: {task.id}")

        # Start background processing
        process_pst_file.delay(str(task.id))

        return UploadResponse(
            task_id=task.id,
            filename=file.filename,
            file_size=file_size,
            message="Upload successful, processing started",
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up on error
        if file_path.exists():
            file_path.unlink()
        logger.error(f"Upload error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    current_user: ActiveUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(None, alias="status"),
) -> TaskListResponse:
    """List processing tasks for the current user."""
    # Build query
    query = select(ProcessingTask).where(ProcessingTask.user_id == current_user.id)

    if status_filter:
        query = query.where(ProcessingTask.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(ProcessingTask.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    tasks = list(result.scalars().all())

    return TaskListResponse(
        tasks=[
            TaskStatusResponse(
                task_id=t.id,
                status=t.status,
                current_phase=t.current_phase,
                progress_percent=t.progress_percent,
                emails_total=t.emails_total,
                emails_processed=t.emails_processed,
                emails_failed=t.emails_failed,
                started_at=t.started_at,
                completed_at=t.completed_at,
                error_message=t.error_message,
                duration_seconds=t.duration_seconds,
                eta_seconds=t.calculate_eta_seconds(),
            )
            for t in tasks
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/tasks/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: UUID,
    current_user: ActiveUser,
    db: DbSession,
) -> TaskDetailResponse:
    """Get detailed information about a processing task."""
    result = await db.execute(
        select(ProcessingTask).where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return TaskDetailResponse(
        task_id=task.id,
        status=task.status,
        current_phase=task.current_phase,
        progress_percent=task.progress_percent,
        emails_total=task.emails_total,
        emails_processed=task.emails_processed,
        emails_failed=task.emails_failed,
        started_at=task.started_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
        duration_seconds=task.duration_seconds,
        eta_seconds=task.calculate_eta_seconds(),
        original_filename=task.original_filename,
        file_size_bytes=task.file_size_bytes,
        sha256_hash=task.sha256_hash,
        md5_hash=task.md5_hash,
        user_id=task.user_id,
        created_at=task.created_at,
    )


@router.post("/tasks/{task_id}/cancel", response_model=CancelTaskResponse)
async def cancel_task(
    task_id: UUID,
    current_user: ActiveUser,
    db: DbSession,
) -> CancelTaskResponse:
    """Cancel a running processing task."""
    result = await db.execute(
        select(ProcessingTask).where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if not task.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task cannot be cancelled (status: {task.status.value})",
        )

    # Trigger cancellation
    cancel_processing.delay(str(task_id))

    return CancelTaskResponse(
        task_id=task_id,
        status="cancelling",
        message="Task cancellation requested",
    )


@router.delete("/tasks/{task_id}", response_model=DeleteTaskResponse)
async def delete_task(
    task_id: UUID,
    current_user: ActiveUser,
    db: DbSession,
    delete_files: bool = Query(True, description="Delete uploaded files"),
) -> DeleteTaskResponse:
    """
    Delete a processing task and optionally its associated data.

    Only completed, failed, or cancelled tasks can be deleted.
    """
    result = await db.execute(
        select(ProcessingTask).where(
            ProcessingTask.id == task_id,
            ProcessingTask.user_id == current_user.id,
        )
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    if task.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete active task. Cancel it first.",
        )

    # Count records to delete
    emails_count = await db.scalar(
        select(func.count()).select_from(Email).where(Email.pst_file_id == task_id)
    )

    attachments_count = await db.scalar(
        select(func.count())
        .select_from(Attachment)
        .join(Email)
        .where(Email.pst_file_id == task_id)
    )

    # Delete attachments
    await db.execute(
        delete(Attachment).where(
            Attachment.email_id.in_(
                select(Email.id).where(Email.pst_file_id == task_id)
            )
        )
    )

    # Delete emails
    await db.execute(delete(Email).where(Email.pst_file_id == task_id))

    # Delete task
    await db.execute(delete(ProcessingTask).where(ProcessingTask.id == task_id))

    await db.commit()

    # Delete embeddings asynchronously
    delete_embeddings_for_task.delay(str(task_id))

    # Delete files
    if delete_files and task.file_path:
        try:
            file_path = Path(task.file_path)
            if file_path.exists():
                file_path.unlink()

            # Delete attachment files
            attachments_dir = Path(settings.upload_dir) / "attachments" / str(task_id)
            if attachments_dir.exists():
                shutil.rmtree(attachments_dir)

        except Exception as e:
            logger.error(f"Error deleting files: {e}")

    logger.info(f"Deleted task {task_id} with {emails_count} emails")

    return DeleteTaskResponse(
        task_id=task_id,
        message="Task deleted successfully",
        emails_deleted=emails_count or 0,
        attachments_deleted=attachments_count or 0,
        embeddings_deleted=True,
    )


# ===========================================
# Admin Endpoints
# ===========================================


@router.get("/admin/tasks", response_model=TaskListResponse)
async def admin_list_all_tasks(
    admin: AdminUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(None, alias="status"),
    user_id: UUID | None = Query(None),
) -> TaskListResponse:
    """List all processing tasks (admin only)."""
    query = select(ProcessingTask)

    if status_filter:
        query = query.where(ProcessingTask.status == status_filter)

    if user_id:
        query = query.where(ProcessingTask.user_id == user_id)

    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.order_by(ProcessingTask.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    tasks = list(result.scalars().all())

    return TaskListResponse(
        tasks=[
            TaskStatusResponse(
                task_id=t.id,
                status=t.status,
                current_phase=t.current_phase,
                progress_percent=t.progress_percent,
                emails_total=t.emails_total,
                emails_processed=t.emails_processed,
                emails_failed=t.emails_failed,
                started_at=t.started_at,
                completed_at=t.completed_at,
                error_message=t.error_message,
                duration_seconds=t.duration_seconds,
                eta_seconds=t.calculate_eta_seconds(),
            )
            for t in tasks
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
