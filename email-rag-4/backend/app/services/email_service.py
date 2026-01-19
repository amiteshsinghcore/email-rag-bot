"""
Email Service

Provides email management capabilities including listing, retrieval,
thread reconstruction, and attachment handling.
"""

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.models.attachment import Attachment
from app.db.models.email import Email
from app.db.session import get_db_context


@dataclass
class EmailSummary:
    """Summary view of an email for list display."""

    id: str
    subject: str | None
    sender_email: str | None
    sender_name: str | None
    sent_date: datetime | None
    has_attachments: bool
    attachment_count: int
    is_read: bool
    importance: str
    folder_path: str | None
    snippet: str | None = None


@dataclass
class AttachmentInfo:
    """Information about an email attachment."""

    id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    is_inline: bool
    has_extracted_text: bool


@dataclass
class EmailDetail:
    """Full email details."""

    id: str
    message_id: str | None
    thread_id: str | None

    # Sender
    sender_email: str | None
    sender_name: str | None

    # Recipients
    to_recipients: list[str]
    cc_recipients: list[str]
    bcc_recipients: list[str]

    # Content
    subject: str | None
    body_text: str | None
    body_html: str | None

    # Dates
    sent_date: datetime | None
    received_date: datetime | None

    # Properties
    importance: str
    is_read: bool
    folder_path: str | None

    # Attachments
    attachments: list[AttachmentInfo]

    # Metadata
    pst_file_id: str
    size_bytes: int | None

    # Threading
    in_reply_to: str | None
    thread_emails: list["EmailSummary"] | None = None


@dataclass
class EmailThread:
    """Email thread with all messages."""

    thread_id: str
    subject: str | None
    participants: list[str]
    email_count: int
    earliest_date: datetime | None
    latest_date: datetime | None
    emails: list[EmailDetail]


@dataclass
class EmailListResponse:
    """Response for email list endpoint."""

    emails: list[EmailSummary]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class EmailService:
    """
    Service for email management operations.

    Provides:
    - Email listing with pagination and filtering
    - Email detail retrieval
    - Thread reconstruction
    - Attachment access
    """

    async def list_emails(
        self,
        pst_file_ids: list[str] | None = None,
        folder_path: str | None = None,
        sender_email: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        has_attachments: bool | None = None,
        importance: str | None = None,
        is_read: bool | None = None,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "sent_date",
        sort_order: str = "desc",
    ) -> EmailListResponse:
        """
        List emails with filtering and pagination.

        Args:
            pst_file_ids: Filter by PST file IDs
            folder_path: Filter by folder path (prefix match)
            sender_email: Filter by sender email
            date_from: Filter emails from this date
            date_to: Filter emails until this date
            has_attachments: Filter by attachment presence
            importance: Filter by importance level
            is_read: Filter by read status
            page: Page number (1-indexed)
            page_size: Number of emails per page
            sort_by: Field to sort by
            sort_order: Sort direction ("asc" or "desc")

        Returns:
            EmailListResponse with emails and pagination info
        """
        async with get_db_context() as db:
            # Build query
            stmt = select(Email).options(selectinload(Email.attachments))

            # Apply filters
            conditions = []

            if pst_file_ids:
                conditions.append(Email.pst_file_id.in_(pst_file_ids))

            if folder_path:
                conditions.append(Email.folder_path.like(f"{folder_path}%"))

            if sender_email:
                conditions.append(Email.sender_email == sender_email)

            if date_from:
                conditions.append(Email.sent_date >= date_from)

            if date_to:
                conditions.append(Email.sent_date <= date_to)

            if has_attachments is not None:
                conditions.append(Email.has_attachments == has_attachments)

            if importance:
                conditions.append(Email.importance == importance)

            if is_read is not None:
                conditions.append(Email.is_read == is_read)

            if conditions:
                stmt = stmt.where(and_(*conditions))

            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = await db.scalar(count_stmt) or 0

            # Apply sorting
            sort_column = getattr(Email, sort_by, Email.sent_date)
            if sort_order == "desc":
                stmt = stmt.order_by(sort_column.desc().nulls_last())
            else:
                stmt = stmt.order_by(sort_column.asc().nulls_first())

            # Apply pagination
            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)

            # Execute
            result = await db.execute(stmt)
            emails = result.scalars().all()

            # Convert to summaries
            summaries = [self._to_summary(email) for email in emails]

            return EmailListResponse(
                emails=summaries,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_more=(page * page_size) < total_count,
            )

    async def get_email(
        self,
        email_id: str,
        include_thread: bool = False,
    ) -> EmailDetail | None:
        """
        Get full email details.

        Args:
            email_id: Email ID to retrieve
            include_thread: Whether to include thread context

        Returns:
            EmailDetail or None if not found
        """
        async with get_db_context() as db:
            stmt = (
                select(Email)
                .options(selectinload(Email.attachments))
                .where(Email.id == email_id)
            )
            result = await db.execute(stmt)
            email = result.scalar_one_or_none()

            if not email:
                return None

            detail = self._to_detail(email)

            # Get thread context if requested
            if include_thread and email.thread_id:
                thread_emails = await self._get_thread_emails(db, email.thread_id, email_id)
                detail.thread_emails = thread_emails

            return detail

    async def get_thread(self, thread_id: str) -> EmailThread | None:
        """
        Get all emails in a thread.

        Args:
            thread_id: Thread ID to retrieve

        Returns:
            EmailThread with all messages or None if not found
        """
        async with get_db_context() as db:
            stmt = (
                select(Email)
                .options(selectinload(Email.attachments))
                .where(Email.thread_id == thread_id)
                .order_by(Email.sent_date.asc())
            )
            result = await db.execute(stmt)
            emails = list(result.scalars().all())

            if not emails:
                return None

            # Build thread info
            participants = set()
            for email in emails:
                if email.sender_email:
                    participants.add(email.sender_email)
                for recipients in [email.to_recipients, email.cc_recipients]:
                    if recipients:
                        participants.update(recipients)

            return EmailThread(
                thread_id=thread_id,
                subject=emails[0].subject,
                participants=list(participants),
                email_count=len(emails),
                earliest_date=emails[0].sent_date,
                latest_date=emails[-1].sent_date,
                emails=[self._to_detail(e) for e in emails],
            )

    async def get_thread_by_email(self, email_id: str) -> EmailThread | None:
        """
        Get thread containing a specific email.

        Args:
            email_id: Email ID to find thread for

        Returns:
            EmailThread or None if email not found or no thread
        """
        async with get_db_context() as db:
            # Get the email to find its thread_id
            stmt = select(Email.thread_id).where(Email.id == email_id)
            result = await db.execute(stmt)
            thread_id = result.scalar_one_or_none()

            if not thread_id:
                return None

            return await self.get_thread(thread_id)

    async def get_attachment(
        self,
        attachment_id: str,
    ) -> tuple[Attachment, bytes] | None:
        """
        Get attachment with content.

        Args:
            attachment_id: Attachment ID to retrieve

        Returns:
            Tuple of (Attachment, bytes) or None if not found
        """
        async with get_db_context() as db:
            stmt = select(Attachment).where(Attachment.id == attachment_id)
            result = await db.execute(stmt)
            attachment = result.scalar_one_or_none()

            if not attachment:
                return None

            # Read file content
            if attachment.storage_path:
                try:
                    file_path = Path(attachment.storage_path)
                    if file_path.exists():
                        content = file_path.read_bytes()
                        return attachment, content
                except Exception as e:
                    logger.error(f"Failed to read attachment file: {e}")

            return None

    async def get_attachment_info(
        self,
        attachment_id: str,
    ) -> AttachmentInfo | None:
        """
        Get attachment metadata without content.

        Args:
            attachment_id: Attachment ID

        Returns:
            AttachmentInfo or None if not found
        """
        async with get_db_context() as db:
            stmt = select(Attachment).where(Attachment.id == attachment_id)
            result = await db.execute(stmt)
            attachment = result.scalar_one_or_none()

            if not attachment:
                return None

            return self._to_attachment_info(attachment)

    async def get_email_attachments(
        self,
        email_id: str,
    ) -> list[AttachmentInfo]:
        """
        Get all attachments for an email.

        Args:
            email_id: Email ID

        Returns:
            List of attachment info
        """
        async with get_db_context() as db:
            stmt = select(Attachment).where(Attachment.email_id == email_id)
            result = await db.execute(stmt)
            attachments = result.scalars().all()

            return [self._to_attachment_info(a) for a in attachments]

    async def mark_as_read(
        self,
        email_id: str,
        is_read: bool = True,
    ) -> bool:
        """
        Mark email as read/unread.

        Args:
            email_id: Email ID
            is_read: Read status to set

        Returns:
            True if updated, False if email not found
        """
        async with get_db_context() as db:
            stmt = select(Email).where(Email.id == email_id)
            result = await db.execute(stmt)
            email = result.scalar_one_or_none()

            if not email:
                return False

            email.is_read = is_read
            await db.commit()
            return True

    async def get_folder_structure(
        self,
        pst_file_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get folder structure with email counts.

        Args:
            pst_file_id: Optional filter by PST file

        Returns:
            List of folder info with counts
        """
        async with get_db_context() as db:
            stmt = (
                select(
                    Email.folder_path,
                    func.count(Email.id).label("count"),
                )
                .group_by(Email.folder_path)
                .order_by(Email.folder_path)
            )

            if pst_file_id:
                stmt = stmt.where(Email.pst_file_id == pst_file_id)

            result = await db.execute(stmt)
            rows = result.all()

            folders = []
            for row in rows:
                if row.folder_path:
                    folders.append({
                        "path": row.folder_path,
                        "name": row.folder_path.split("/")[-1] if "/" in row.folder_path else row.folder_path,
                        "email_count": row.count,
                    })

            return folders

    async def get_email_stats(
        self,
        pst_file_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get email statistics.

        Args:
            pst_file_id: Optional filter by PST file

        Returns:
            Dictionary with email statistics
        """
        async with get_db_context() as db:
            base_condition = Email.pst_file_id == pst_file_id if pst_file_id else True

            # Total count
            total = await db.scalar(
                select(func.count(Email.id)).where(base_condition)
            ) or 0

            # With attachments
            with_attachments = await db.scalar(
                select(func.count(Email.id))
                .where(and_(base_condition, Email.has_attachments == True))
            ) or 0

            # Date range
            date_result = await db.execute(
                select(
                    func.min(Email.sent_date).label("earliest"),
                    func.max(Email.sent_date).label("latest"),
                ).where(base_condition)
            )
            date_row = date_result.one()

            # Top senders
            sender_result = await db.execute(
                select(
                    Email.sender_email,
                    func.count(Email.id).label("count"),
                )
                .where(base_condition)
                .group_by(Email.sender_email)
                .order_by(func.count(Email.id).desc())
                .limit(10)
            )
            top_senders = [
                {"email": row.sender_email, "count": row.count}
                for row in sender_result
                if row.sender_email
            ]

            return {
                "total_emails": total,
                "with_attachments": with_attachments,
                "earliest_date": date_row.earliest.isoformat() if date_row.earliest else None,
                "latest_date": date_row.latest.isoformat() if date_row.latest else None,
                "top_senders": top_senders,
            }

    async def _get_thread_emails(
        self,
        db: AsyncSession,
        thread_id: str,
        exclude_email_id: str,
    ) -> list[EmailSummary]:
        """Get other emails in a thread."""
        stmt = (
            select(Email)
            .where(and_(
                Email.thread_id == thread_id,
                Email.id != exclude_email_id,
            ))
            .order_by(Email.sent_date.asc())
            .limit(50)  # Limit thread context
        )
        result = await db.execute(stmt)
        emails = result.scalars().all()

        return [self._to_summary(e) for e in emails]

    def _to_summary(self, email: Email) -> EmailSummary:
        """Convert Email model to EmailSummary."""
        # Generate snippet from body
        snippet = None
        if email.body_text:
            snippet = email.body_text[:200].replace("\n", " ").strip()

        return EmailSummary(
            id=str(email.id),
            subject=email.subject,
            sender_email=email.sender_email,
            sender_name=email.sender_name,
            sent_date=email.sent_date,
            has_attachments=email.has_attachments,
            attachment_count=len(email.attachments) if email.attachments else 0,
            is_read=email.is_read,
            importance=email.importance,
            folder_path=email.folder_path,
            snippet=snippet,
        )

    def _to_detail(self, email: Email) -> EmailDetail:
        """Convert Email model to EmailDetail."""
        attachments = [
            self._to_attachment_info(a)
            for a in (email.attachments or [])
        ]

        return EmailDetail(
            id=str(email.id),
            message_id=email.message_id,
            thread_id=email.thread_id,
            sender_email=email.sender_email,
            sender_name=email.sender_name,
            to_recipients=email.to_recipients or [],
            cc_recipients=email.cc_recipients or [],
            bcc_recipients=email.bcc_recipients or [],
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            sent_date=email.sent_date,
            received_date=email.received_date,
            importance=email.importance,
            is_read=email.is_read,
            folder_path=email.folder_path,
            attachments=attachments,
            pst_file_id=str(email.pst_file_id),
            size_bytes=email.size_bytes,
            in_reply_to=email.in_reply_to,
        )

    def _to_attachment_info(self, attachment: Attachment) -> AttachmentInfo:
        """Convert Attachment model to AttachmentInfo."""
        return AttachmentInfo(
            id=str(attachment.id),
            filename=attachment.filename,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
            is_inline=attachment.is_inline,
            has_extracted_text=bool(attachment.extracted_text),
        )


# Global instance
email_service = EmailService()


def get_email_service() -> EmailService:
    """Get the email service instance."""
    return email_service
