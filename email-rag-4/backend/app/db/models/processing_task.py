"""
Processing Task Database Model

Tracks PST file uploads and processing status.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.email import Email
    from app.db.models.user import User


class TaskStatus(str, Enum):
    """Processing task status."""

    PENDING = "pending"
    UPLOADING = "uploading"
    VALIDATING = "validating"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingTask(Base, UUIDMixin, TimestampMixin):
    """PST file processing task."""

    __tablename__ = "processing_tasks"

    # User who uploaded
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # File information
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )
    file_size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Forensic integrity
    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    md5_hash: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )

    # Processing status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=TaskStatus.PENDING.value,
        index=True,
    )
    current_phase: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Progress tracking
    progress_percent: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    emails_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    emails_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    emails_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    attachments_total: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    attachments_processed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Celery task reference
    celery_task_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Metadata
    pst_display_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    pst_created_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    pst_modified_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="processing_tasks",
    )
    emails: Mapped[list["Email"]] = relationship(
        "Email",
        back_populates="pst_file",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # Indexes
    __table_args__ = (
        Index("ix_processing_tasks_user_status", "user_id", "status"),
        Index("ix_processing_tasks_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ProcessingTask(id={self.id}, status={self.status}, file={self.original_filename})>"

    @property
    def is_active(self) -> bool:
        """Check if task is currently active."""
        return self.status in (
            TaskStatus.PENDING.value,
            TaskStatus.UPLOADING.value,
            TaskStatus.VALIDATING.value,
            TaskStatus.PARSING.value,
            TaskStatus.EXTRACTING.value,
            TaskStatus.EMBEDDING.value,
            TaskStatus.INDEXING.value,
        )

    @property
    def is_complete(self) -> bool:
        """Check if task has completed (success or failure)."""
        return self.status in (
            TaskStatus.COMPLETED.value,
            TaskStatus.FAILED.value,
            TaskStatus.CANCELLED.value,
        )

    @property
    def duration_seconds(self) -> float | None:
        """Get processing duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now(self.started_at.tzinfo)
        return (end_time - self.started_at).total_seconds()

    @property
    def emails_per_minute(self) -> float | None:
        """Calculate processing rate."""
        duration = self.duration_seconds
        if duration is None or duration == 0 or self.emails_processed == 0:
            return None
        return (self.emails_processed / duration) * 60

    def calculate_eta_seconds(self) -> float | None:
        """Estimate time remaining based on current progress."""
        if self.emails_total is None or self.emails_total == 0:
            return None
        if self.emails_processed == 0:
            return None

        duration = self.duration_seconds
        if duration is None or duration == 0:
            return None

        rate = self.emails_processed / duration
        remaining = self.emails_total - self.emails_processed
        return remaining / rate if rate > 0 else None
