"""
Email Schemas

Pydantic schemas for email request/response validation.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AttachmentSchema(BaseModel):
    """Attachment information schema."""

    id: str
    filename: str
    content_type: str | None
    size_bytes: int | None
    is_inline: bool = False
    has_extracted_text: bool = False


class EmailSummarySchema(BaseModel):
    """Email summary for list display."""

    id: str
    subject: str | None
    sender_email: str | None
    sender_name: str | None
    sent_date: datetime | None
    has_attachments: bool = False
    attachment_count: int = 0
    is_read: bool = False
    importance: str = "normal"
    folder_path: str | None = None
    snippet: str | None = None


class EmailDetailSchema(BaseModel):
    """Full email details."""

    id: str
    message_id: str | None = None
    thread_id: str | None = None

    # Sender
    sender_email: str | None = None
    sender_name: str | None = None

    # Recipients
    to_recipients: list[str] = []
    cc_recipients: list[str] = []
    bcc_recipients: list[str] = []

    # Content
    subject: str | None = None
    body_text: str | None = None
    body_html: str | None = None

    # Dates
    sent_date: datetime | None = None
    received_date: datetime | None = None

    # Properties
    importance: str = "normal"
    is_read: bool = False
    folder_path: str | None = None

    # Attachments
    attachments: list[AttachmentSchema] = []

    # Metadata
    pst_file_id: str
    size_bytes: int | None = None

    # Threading
    in_reply_to: str | None = None
    thread_emails: list[EmailSummarySchema] | None = None


class EmailThreadSchema(BaseModel):
    """Email thread with all messages."""

    thread_id: str
    subject: str | None
    participants: list[str] = []
    email_count: int
    earliest_date: datetime | None = None
    latest_date: datetime | None = None
    emails: list[EmailDetailSchema] = []


class EmailListRequest(BaseModel):
    """Email list request with filters."""

    pst_file_ids: list[str] | None = Field(
        default=None,
        description="Filter by PST file IDs",
    )
    folder_path: str | None = Field(
        default=None,
        description="Filter by folder path (prefix match)",
    )
    sender_email: str | None = Field(
        default=None,
        description="Filter by sender email",
    )
    date_from: datetime | None = Field(
        default=None,
        description="Filter emails from this date",
    )
    date_to: datetime | None = Field(
        default=None,
        description="Filter emails until this date",
    )
    has_attachments: bool | None = Field(
        default=None,
        description="Filter by attachment presence",
    )
    importance: str | None = Field(
        default=None,
        description="Filter by importance level",
    )
    is_read: bool | None = Field(
        default=None,
        description="Filter by read status",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number",
    )
    page_size: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Emails per page",
    )
    sort_by: str = Field(
        default="sent_date",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        description="Sort order: 'asc' or 'desc'",
    )


class EmailListResponse(BaseModel):
    """Email list response."""

    emails: list[EmailSummarySchema]
    total_count: int
    page: int
    page_size: int
    has_more: bool


class MarkReadRequest(BaseModel):
    """Request to mark email as read/unread."""

    is_read: bool = Field(
        default=True,
        description="Read status to set",
    )


class FolderSchema(BaseModel):
    """Folder information."""

    path: str
    name: str
    email_count: int


class FolderListResponse(BaseModel):
    """Folder list response."""

    folders: list[FolderSchema]


class EmailStatsResponse(BaseModel):
    """Email statistics response."""

    total_emails: int
    with_attachments: int
    earliest_date: str | None = None
    latest_date: str | None = None
    top_senders: list[dict[str, int | str]] = []
