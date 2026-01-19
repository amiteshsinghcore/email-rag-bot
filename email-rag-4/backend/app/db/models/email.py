"""
Email Database Model

Stores extracted email data from PST files with full metadata.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.attachment import Attachment
    from app.db.models.processing_task import ProcessingTask


class EmailImportance(str, Enum):
    """Email importance/priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Email(Base, UUIDMixin, TimestampMixin):
    """Email record extracted from PST file."""

    __tablename__ = "emails"

    # PST source reference
    pst_file_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("processing_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Core email identifiers
    message_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
    )
    internet_message_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
    )

    # Threading
    thread_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        index=True,
    )
    in_reply_to: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    references: Mapped[str | None] = mapped_column(
        Text,  # Can be very long
        nullable=True,
    )
    thread_index: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Sender information
    sender_email: Mapped[str | None] = mapped_column(
        String(320),  # Max email length per RFC
        nullable=True,
        index=True,
    )
    sender_name: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Recipients (stored as arrays)
    to_recipients: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(320)),
        nullable=True,
    )
    cc_recipients: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(320)),
        nullable=True,
    )
    bcc_recipients: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(320)),
        nullable=True,
    )

    # Email content
    subject: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    body_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    body_html: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Dates
    sent_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    received_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    # Email properties
    importance: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EmailImportance.NORMAL.value,
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    has_attachments: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    # Folder information
    folder_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        index=True,
    )

    # Headers (full headers for forensics)
    headers: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Forensic data
    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # Size in bytes
    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Full-text search vector
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    # Embedding status
    is_embedded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    embedding_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Relationships
    pst_file: Mapped["ProcessingTask"] = relationship(
        "ProcessingTask",
        back_populates="emails",
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="email",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Indexes
    __table_args__ = (
        # Composite index for common queries
        Index("ix_emails_pst_sent_date", "pst_file_id", "sent_date"),
        Index("ix_emails_sender_date", "sender_email", "sent_date"),
        # GIN index for full-text search
        Index(
            "ix_emails_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        # Partial index for unembedded emails
        Index(
            "ix_emails_not_embedded",
            "id",
            postgresql_where="is_embedded = false",
        ),
    )

    def __repr__(self) -> str:
        return f"<Email(id={self.id}, subject={self.subject[:50] if self.subject else 'None'})>"

    @property
    def all_recipients(self) -> list[str]:
        """Get all recipients (to, cc, bcc combined)."""
        recipients = []
        if self.to_recipients:
            recipients.extend(self.to_recipients)
        if self.cc_recipients:
            recipients.extend(self.cc_recipients)
        if self.bcc_recipients:
            recipients.extend(self.bcc_recipients)
        return recipients

    @property
    def participant_emails(self) -> set[str]:
        """Get all unique email addresses involved in this email."""
        participants = set()
        if self.sender_email:
            participants.add(self.sender_email.lower())
        for recipient in self.all_recipients:
            participants.add(recipient.lower())
        return participants
