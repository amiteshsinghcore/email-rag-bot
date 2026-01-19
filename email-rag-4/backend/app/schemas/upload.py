"""
Upload Schemas

Request and response schemas for file upload and processing.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.processing_task import TaskStatus


class UploadResponse(BaseModel):
    """Response after successful file upload."""

    task_id: UUID = Field(..., description="Processing task ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    message: str = Field(default="Upload successful, processing started")


class ChunkUploadInitRequest(BaseModel):
    """Request to initialize a chunked upload."""
    
    filename: str
    total_size: int
    total_chunks: int


class ChunkUploadInitResponse(BaseModel):
    """Response for chunked upload initialization."""

    upload_id: str
    chunk_size: int = 95 * 1024 * 1024  # Default 95MB


class TaskStatusResponse(BaseModel):
    """Processing task status response."""

    task_id: UUID
    status: TaskStatus
    current_phase: str | None = None
    progress_percent: float
    emails_total: int
    emails_processed: int
    emails_failed: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    duration_seconds: float | None = None
    eta_seconds: float | None = None

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    """List of processing tasks."""

    tasks: list[TaskStatusResponse]
    total: int
    page: int
    page_size: int


class TaskDetailResponse(TaskStatusResponse):
    """Detailed task information."""

    original_filename: str
    file_size_bytes: int
    sha256_hash: str | None = None
    md5_hash: str | None = None
    user_id: UUID
    created_at: datetime


class CancelTaskResponse(BaseModel):
    """Response after cancelling a task."""

    task_id: UUID
    status: str
    message: str


class DeleteTaskResponse(BaseModel):
    """Response after deleting a task."""

    task_id: UUID
    message: str
    emails_deleted: int = 0
    attachments_deleted: int = 0
    embeddings_deleted: bool = False
