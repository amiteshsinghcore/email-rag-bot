"""
Evidence Database Model

Tracks forensic evidence integrity and chain of custody.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class EvidenceAction(str, Enum):
    """Types of evidence actions for audit trail."""

    REGISTERED = "registered"
    ACCESSED = "accessed"
    SEARCHED = "searched"
    EXPORTED = "exported"
    VERIFIED = "verified"
    MODIFIED = "modified"


class Evidence(Base, UUIDMixin, TimestampMixin):
    """
    Evidence registration record.

    Tracks the chain of custody for PST files and ensures forensic integrity.
    """

    __tablename__ = "evidences"

    # Reference to processing task (PST file)
    processing_task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("processing_tasks.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Evidence identification
    evidence_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    case_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    case_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Custodian information
    custodian_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    custodian_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    # Source information
    source_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    collection_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    collected_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Integrity verification
    sha256_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    md5_hash: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="verified",
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, evidence_number={self.evidence_number})>"


class AuditLog(Base, UUIDMixin):
    """
    Immutable audit log for all evidence-related actions.

    This table is append-only and should never be updated or deleted.
    """

    __tablename__ = "audit_logs"

    # When the action occurred
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Who performed the action
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )
    user_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # What action was performed
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # What resource was affected
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Additional context
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Request context
    request_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_timestamp_action", "timestamp", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_user_timestamp", "user_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, resource={self.resource_type})>"
