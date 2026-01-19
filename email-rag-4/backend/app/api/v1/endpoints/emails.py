"""
Email API Endpoints

Endpoints for email management, retrieval, and attachment handling.
"""

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from loguru import logger

from app.api.deps import CurrentUser
from app.schemas.email import (
    AttachmentSchema,
    EmailDetailSchema,
    EmailListRequest,
    EmailListResponse,
    EmailStatsResponse,
    EmailSummarySchema,
    EmailThreadSchema,
    FolderListResponse,
    FolderSchema,
    MarkReadRequest,
)
from app.services.email_service import get_email_service

router = APIRouter(prefix="/emails", tags=["Emails"])


@router.post(
    "",
    response_model=EmailListResponse,
    summary="List emails",
    description="List emails with filtering and pagination.",
)
async def list_emails(
    request: EmailListRequest,
    current_user: CurrentUser,
) -> EmailListResponse:
    """
    List emails with filtering and pagination.

    Supports filtering by PST file, folder, sender, date range,
    attachments, importance, and read status.
    """
    email_service = get_email_service()

    try:
        result = await email_service.list_emails(
            pst_file_ids=request.pst_file_ids,
            folder_path=request.folder_path,
            sender_email=request.sender_email,
            date_from=request.date_from,
            date_to=request.date_to,
            has_attachments=request.has_attachments,
            importance=request.importance,
            is_read=request.is_read,
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )

        # Convert to response schema
        emails = [
            EmailSummarySchema(
                id=e.id,
                subject=e.subject,
                sender_email=e.sender_email,
                sender_name=e.sender_name,
                sent_date=e.sent_date,
                has_attachments=e.has_attachments,
                attachment_count=e.attachment_count,
                is_read=e.is_read,
                importance=e.importance,
                folder_path=e.folder_path,
                snippet=e.snippet,
            )
            for e in result.emails
        ]

        return EmailListResponse(
            emails=emails,
            total_count=result.total_count,
            page=result.page,
            page_size=result.page_size,
            has_more=result.has_more,
        )

    except Exception as e:
        logger.exception(f"Failed to list emails: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to list emails", "message": str(e)},
        )


@router.get(
    "/{email_id}",
    response_model=EmailDetailSchema,
    summary="Get email",
    description="Get full email details including body and attachments.",
)
async def get_email(
    email_id: str,
    current_user: CurrentUser,
    include_thread: bool = Query(
        default=False,
        description="Include thread context",
    ),
) -> EmailDetailSchema:
    """
    Get full email details.

    Returns the complete email including body content,
    attachment list, and optionally thread context.
    """
    email_service = get_email_service()

    try:
        email = await email_service.get_email(
            email_id=email_id,
            include_thread=include_thread,
        )

        if not email:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Email not found"},
            )

        # Convert attachments
        attachments = [
            AttachmentSchema(
                id=a.id,
                filename=a.filename,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                is_inline=a.is_inline,
                has_extracted_text=a.has_extracted_text,
            )
            for a in email.attachments
        ]

        # Convert thread emails if present
        thread_emails = None
        if email.thread_emails:
            thread_emails = [
                EmailSummarySchema(
                    id=e.id,
                    subject=e.subject,
                    sender_email=e.sender_email,
                    sender_name=e.sender_name,
                    sent_date=e.sent_date,
                    has_attachments=e.has_attachments,
                    attachment_count=e.attachment_count,
                    is_read=e.is_read,
                    importance=e.importance,
                    folder_path=e.folder_path,
                    snippet=e.snippet,
                )
                for e in email.thread_emails
            ]

        return EmailDetailSchema(
            id=email.id,
            message_id=email.message_id,
            thread_id=email.thread_id,
            sender_email=email.sender_email,
            sender_name=email.sender_name,
            to_recipients=email.to_recipients,
            cc_recipients=email.cc_recipients,
            bcc_recipients=email.bcc_recipients,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            sent_date=email.sent_date,
            received_date=email.received_date,
            importance=email.importance,
            is_read=email.is_read,
            folder_path=email.folder_path,
            attachments=attachments,
            pst_file_id=email.pst_file_id,
            size_bytes=email.size_bytes,
            in_reply_to=email.in_reply_to,
            thread_emails=thread_emails,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get email", "message": str(e)},
        )


@router.get(
    "/{email_id}/thread",
    response_model=EmailThreadSchema,
    summary="Get email thread",
    description="Get all emails in the thread containing this email.",
)
async def get_email_thread(
    email_id: str,
    current_user: CurrentUser,
) -> EmailThreadSchema:
    """
    Get the complete email thread.

    Returns all emails in the conversation thread,
    ordered chronologically.
    """
    email_service = get_email_service()

    try:
        thread = await email_service.get_thread_by_email(email_id=email_id)

        if not thread:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Thread not found or email has no thread"},
            )

        # Convert emails
        emails = []
        for e in thread.emails:
            attachments = [
                AttachmentSchema(
                    id=a.id,
                    filename=a.filename,
                    content_type=a.content_type,
                    size_bytes=a.size_bytes,
                    is_inline=a.is_inline,
                    has_extracted_text=a.has_extracted_text,
                )
                for a in e.attachments
            ]

            emails.append(
                EmailDetailSchema(
                    id=e.id,
                    message_id=e.message_id,
                    thread_id=e.thread_id,
                    sender_email=e.sender_email,
                    sender_name=e.sender_name,
                    to_recipients=e.to_recipients,
                    cc_recipients=e.cc_recipients,
                    bcc_recipients=e.bcc_recipients,
                    subject=e.subject,
                    body_text=e.body_text,
                    body_html=e.body_html,
                    sent_date=e.sent_date,
                    received_date=e.received_date,
                    importance=e.importance,
                    is_read=e.is_read,
                    folder_path=e.folder_path,
                    attachments=attachments,
                    pst_file_id=e.pst_file_id,
                    size_bytes=e.size_bytes,
                    in_reply_to=e.in_reply_to,
                )
            )

        return EmailThreadSchema(
            thread_id=thread.thread_id,
            subject=thread.subject,
            participants=thread.participants,
            email_count=thread.email_count,
            earliest_date=thread.earliest_date,
            latest_date=thread.latest_date,
            emails=emails,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get thread: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get thread", "message": str(e)},
        )


@router.patch(
    "/{email_id}/read",
    summary="Mark email as read/unread",
    description="Update the read status of an email.",
)
async def mark_email_read(
    email_id: str,
    request: MarkReadRequest,
    current_user: CurrentUser,
) -> dict[str, bool]:
    """
    Mark email as read or unread.
    """
    email_service = get_email_service()

    try:
        success = await email_service.mark_as_read(
            email_id=email_id,
            is_read=request.is_read,
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Email not found"},
            )

        return {"success": True, "is_read": request.is_read}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update read status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to update read status"},
        )


@router.get(
    "/{email_id}/attachments",
    response_model=list[AttachmentSchema],
    summary="List email attachments",
    description="Get all attachments for an email.",
)
async def list_email_attachments(
    email_id: str,
    current_user: CurrentUser,
) -> list[AttachmentSchema]:
    """
    List all attachments for an email.
    """
    email_service = get_email_service()

    try:
        attachments = await email_service.get_email_attachments(email_id=email_id)

        return [
            AttachmentSchema(
                id=a.id,
                filename=a.filename,
                content_type=a.content_type,
                size_bytes=a.size_bytes,
                is_inline=a.is_inline,
                has_extracted_text=a.has_extracted_text,
            )
            for a in attachments
        ]

    except Exception as e:
        logger.exception(f"Failed to list attachments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to list attachments"},
        )


@router.get(
    "/attachments/{attachment_id}",
    summary="Download attachment",
    description="Download an attachment file.",
)
async def download_attachment(
    attachment_id: str,
    current_user: CurrentUser,
) -> Response:
    """
    Download an attachment file.

    Returns the attachment content with appropriate content-type.
    """
    email_service = get_email_service()

    try:
        result = await email_service.get_attachment(attachment_id=attachment_id)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Attachment not found"},
            )

        attachment, content = result

        return Response(
            content=content,
            media_type=attachment.content_type or "application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{attachment.filename}"',
                "Content-Length": str(len(content)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to download attachment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to download attachment"},
        )


@router.get(
    "/attachments/{attachment_id}/info",
    response_model=AttachmentSchema,
    summary="Get attachment info",
    description="Get attachment metadata without downloading.",
)
async def get_attachment_info(
    attachment_id: str,
    current_user: CurrentUser,
) -> AttachmentSchema:
    """
    Get attachment metadata.
    """
    email_service = get_email_service()

    try:
        attachment = await email_service.get_attachment_info(attachment_id=attachment_id)

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "Attachment not found"},
            )

        return AttachmentSchema(
            id=attachment.id,
            filename=attachment.filename,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
            is_inline=attachment.is_inline,
            has_extracted_text=attachment.has_extracted_text,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get attachment info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get attachment info"},
        )


@router.get(
    "/folders",
    response_model=FolderListResponse,
    summary="Get folder structure",
    description="Get email folder structure with counts.",
)
async def get_folders(
    current_user: CurrentUser,
    pst_file_id: str | None = Query(
        default=None,
        description="Filter by PST file ID",
    ),
) -> FolderListResponse:
    """
    Get email folder structure.

    Returns all folders with email counts.
    """
    email_service = get_email_service()

    try:
        folders = await email_service.get_folder_structure(pst_file_id=pst_file_id)

        return FolderListResponse(
            folders=[
                FolderSchema(
                    path=f["path"],
                    name=f["name"],
                    email_count=f["email_count"],
                )
                for f in folders
            ]
        )

    except Exception as e:
        logger.exception(f"Failed to get folders: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get folders"},
        )


@router.get(
    "/stats",
    response_model=EmailStatsResponse,
    summary="Get email statistics",
    description="Get email statistics and analytics.",
)
async def get_email_stats(
    current_user: CurrentUser,
    pst_file_id: str | None = Query(
        default=None,
        description="Filter by PST file ID",
    ),
) -> EmailStatsResponse:
    """
    Get email statistics.

    Returns counts, date ranges, and top senders.
    """
    email_service = get_email_service()

    try:
        stats = await email_service.get_email_stats(pst_file_id=pst_file_id)

        return EmailStatsResponse(
            total_emails=stats["total_emails"],
            with_attachments=stats["with_attachments"],
            earliest_date=stats["earliest_date"],
            latest_date=stats["latest_date"],
            top_senders=stats["top_senders"],
        )

    except Exception as e:
        logger.exception(f"Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get statistics"},
        )
