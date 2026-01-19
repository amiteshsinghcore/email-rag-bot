"""
Attachment Database Model

Stores email attachments with metadata and extracted text content.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.email import Email


class Attachment(Base, UUIDMixin, TimestampMixin):
    """Email attachment record."""

    __tablename__ = "attachments"

    # Parent email reference
    email_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("emails.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # File information
    filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    content_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Hashes for forensics and deduplication
    md5_hash: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        index=True,
    )
    sha256_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # Storage location
    storage_path: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    # Extracted text content (for searchable attachments)
    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    text_extraction_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Processing flags
    is_extracted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_embedded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    embedding_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Attachment-specific metadata
    is_inline: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    content_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Relationships
    email: Mapped["Email"] = relationship(
        "Email",
        back_populates="attachments",
    )

    # Indexes
    __table_args__ = (
        # Index for finding attachments by type
        Index("ix_attachments_content_type", "content_type"),
        # Index for finding unprocessed attachments
        Index(
            "ix_attachments_not_extracted",
            "id",
            postgresql_where="is_extracted = false",
        ),
    )

    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, filename={self.filename})>"

    @property
    def extension(self) -> str | None:
        """Get file extension from filename."""
        if "." in self.filename:
            return self.filename.rsplit(".", 1)[-1].lower()
        return None

    @property
    def is_document(self) -> bool:
        """Check if attachment is a document type."""
        doc_extensions = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "rtf"}
        return self.extension in doc_extensions if self.extension else False

    @property
    def is_image(self) -> bool:
        """Check if attachment is an image."""
        image_extensions = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "webp", "svg"}
        return self.extension in image_extensions if self.extension else False
