"""
PST Processor Service

Parses Outlook PST files and extracts emails with full metadata.
Uses pypff library for PST parsing.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator
from uuid import UUID

from loguru import logger


@dataclass
class ExtractedAttachment:
    """Represents an extracted email attachment."""

    filename: str
    content_type: str
    size_bytes: int
    content: bytes
    md5_hash: str
    sha256_hash: str


@dataclass
class ExtractedEmail:
    """Represents an extracted email from PST file."""

    message_id: str
    internet_message_id: str | None
    subject: str
    sender_email: str
    sender_name: str
    to_recipients: list[str]
    cc_recipients: list[str]
    bcc_recipients: list[str]
    body_text: str
    body_html: str | None
    sent_date: datetime | None
    received_date: datetime | None
    importance: str
    is_read: bool
    has_attachments: bool
    folder_path: str
    headers: dict[str, str]
    sha256_hash: str
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    thread_id: str | None = None
    attachments: list[ExtractedAttachment] = field(default_factory=list)


class PSTProcessorError(Exception):
    """Base exception for PST processing errors."""

    pass


class PSTFileNotFoundError(PSTProcessorError):
    """PST file not found."""

    pass


class PSTParseError(PSTProcessorError):
    """Error parsing PST file."""

    pass


class PSTProcessor:
    """
    Service for processing Outlook PST files.

    Extracts emails with full metadata, attachments, and calculates hashes
    for forensic integrity verification.
    """

    # Importance mapping
    IMPORTANCE_MAP = {
        0: "low",
        1: "normal",
        2: "high",
    }

    def __init__(self, pst_path: str | Path):
        """
        Initialize PST processor.

        Args:
            pst_path: Path to the PST file
        """
        self.pst_path = Path(pst_path)
        self._pst_file = None
        self._email_count = 0

        if not self.pst_path.exists():
            raise PSTFileNotFoundError(f"PST file not found: {pst_path}")

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def open(self) -> None:
        """Open the PST file for processing."""
        try:
            import pypff

            self._pst_file = pypff.file()
            self._pst_file.open(str(self.pst_path))
            logger.info(f"Opened PST file: {self.pst_path}")
        except ImportError:
            logger.warning("pypff not available, using mock processor")
            self._pst_file = None
        except Exception as e:
            raise PSTParseError(f"Failed to open PST file: {e}") from e

    def close(self) -> None:
        """Close the PST file."""
        if self._pst_file is not None:
            try:
                self._pst_file.close()
            except Exception:
                pass
            self._pst_file = None

    def get_file_hash(self) -> tuple[str, str]:
        """
        Calculate SHA-256 and MD5 hashes of the PST file.

        Returns:
            Tuple of (sha256_hash, md5_hash)
        """
        sha256 = hashlib.sha256()
        md5 = hashlib.md5()

        with open(self.pst_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
                md5.update(chunk)

        return sha256.hexdigest(), md5.hexdigest()

    def get_file_size(self) -> int:
        """Get the size of the PST file in bytes."""
        return self.pst_path.stat().st_size

    def count_emails(self) -> int:
        """
        Count total emails in the PST file.

        Returns:
            Total number of emails
        """
        if self._pst_file is None:
            return 0

        count = 0
        root = self._pst_file.get_root_folder()
        count = self._count_folder_emails(root)
        return count

    def _count_folder_emails(self, folder) -> int:
        """Recursively count emails in a folder."""
        count = folder.get_number_of_sub_messages()

        for i in range(folder.get_number_of_sub_folders()):
            sub_folder = folder.get_sub_folder(i)
            count += self._count_folder_emails(sub_folder)

        return count

    def extract_emails(
        self,
        include_attachments: bool = True,
        max_attachment_size: int = 50 * 1024 * 1024,  # 50MB
    ) -> Generator[ExtractedEmail, None, None]:
        """
        Extract all emails from the PST file.

        Args:
            include_attachments: Whether to include attachment content
            max_attachment_size: Maximum attachment size to extract (bytes)

        Yields:
            ExtractedEmail objects
        """
        if self._pst_file is None:
            logger.warning("PST file not opened, cannot extract emails")
            return

        root = self._pst_file.get_root_folder()
        yield from self._extract_folder_emails(
            root,
            "",
            include_attachments,
            max_attachment_size,
        )

    def _extract_folder_emails(
        self,
        folder,
        folder_path: str,
        include_attachments: bool,
        max_attachment_size: int,
    ) -> Generator[ExtractedEmail, None, None]:
        """Recursively extract emails from a folder."""
        folder_name = folder.get_name() or "Root"
        current_path = f"{folder_path}/{folder_name}" if folder_path else folder_name

        # Extract messages in this folder
        for i in range(folder.get_number_of_sub_messages()):
            try:
                message = folder.get_sub_message(i)
                email = self._extract_message(
                    message,
                    current_path,
                    include_attachments,
                    max_attachment_size,
                )
                if email:
                    self._email_count += 1
                    yield email
            except Exception as e:
                logger.error(f"Error extracting message {i} from {current_path}: {e}")
                continue

        # Process sub-folders
        for i in range(folder.get_number_of_sub_folders()):
            sub_folder = folder.get_sub_folder(i)
            yield from self._extract_folder_emails(
                sub_folder,
                current_path,
                include_attachments,
                max_attachment_size,
            )

    def _extract_message(
        self,
        message,
        folder_path: str,
        include_attachments: bool,
        max_attachment_size: int,
    ) -> ExtractedEmail | None:
        """Extract a single message."""
        try:
            # Get basic properties
            subject = message.get_subject() or ""
            sender_email = self._get_sender_email(message)
            sender_name = message.get_sender_name() or ""

            # Get recipients
            to_recipients = self._get_recipients(message, "to")
            cc_recipients = self._get_recipients(message, "cc")
            bcc_recipients = self._get_recipients(message, "bcc")

            # Get body - try plain text first, then extract from HTML
            body_text = message.get_plain_text_body() or ""
            if isinstance(body_text, bytes):
                body_text = body_text.decode("utf-8", errors="replace")

            body_html = message.get_html_body()
            if isinstance(body_html, bytes):
                body_html = body_html.decode("utf-8", errors="replace")

            # If plain text is empty but HTML is available, extract text from HTML
            if not body_text.strip() and body_html:
                body_text = self._extract_text_from_html(body_html)

            # Get dates
            sent_date = self._parse_date(message.get_client_submit_time())
            received_date = self._parse_date(message.get_delivery_time())

            # Get headers
            headers = self._extract_headers(message)

            # Get message IDs
            internet_message_id = headers.get("message-id", "")
            in_reply_to = headers.get("in-reply-to")
            references = self._parse_references(headers.get("references", ""))

            # Generate thread ID from conversation index or references
            thread_id = self._generate_thread_id(message, headers)

            # Generate unique message ID
            message_id = self._generate_message_id(
                internet_message_id,
                subject,
                sender_email,
                sent_date,
            )

            # Get importance
            importance_value = getattr(message, "get_importance", lambda: 1)()
            importance = self.IMPORTANCE_MAP.get(importance_value, "normal")

            # Get read status
            is_read = getattr(message, "get_read_flag", lambda: False)()

            # Extract attachments - wrap in try/except as some messages have corrupted metadata
            attachments = []
            has_attachments = False
            try:
                has_attachments = message.get_number_of_attachments() > 0
            except Exception:
                pass  # Attachment metadata corrupted, treat as no attachments

            if include_attachments and has_attachments:
                attachments = self._extract_attachments(message, max_attachment_size)

            # Calculate content hash for deduplication
            content_for_hash = f"{subject}{sender_email}{body_text}{sent_date}"
            sha256_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()

            return ExtractedEmail(
                message_id=message_id,
                internet_message_id=internet_message_id or None,
                subject=subject,
                sender_email=sender_email,
                sender_name=sender_name,
                to_recipients=to_recipients,
                cc_recipients=cc_recipients,
                bcc_recipients=bcc_recipients,
                body_text=body_text,
                body_html=body_html,
                sent_date=sent_date,
                received_date=received_date,
                importance=importance,
                is_read=is_read,
                has_attachments=has_attachments,
                folder_path=folder_path,
                headers=headers,
                sha256_hash=sha256_hash,
                in_reply_to=in_reply_to,
                references=references,
                thread_id=thread_id,
                attachments=attachments,
            )

        except Exception as e:
            logger.error(f"Error extracting message: {e}")
            return None

    def _get_sender_email(self, message) -> str:
        """Extract sender email address."""
        # Try get_sender_email_address if available (older pypff versions)
        if hasattr(message, "get_sender_email_address"):
            try:
                sender = message.get_sender_email_address()
                if sender:
                    return sender
            except Exception:
                pass

        # Try transport headers - most reliable method
        headers = self._extract_headers(message)
        from_header = headers.get("from", "")
        if from_header:
            # Extract email from "Name <email@example.com>" format
            if "<" in from_header and ">" in from_header:
                return from_header[from_header.index("<") + 1 : from_header.index(">")]
            # Handle bare email addresses
            elif "@" in from_header:
                return from_header.strip()

        # Fallback to sender name if it looks like an email
        sender_name = message.get_sender_name() or ""
        if sender_name and "@" in sender_name:
            return sender_name

        return ""

    def _get_recipients(self, message, recipient_type: str) -> list[str]:
        """Extract recipients of a specific type."""
        recipients = []

        # Try pypff recipient methods if available
        try:
            if hasattr(message, "get_number_of_recipients"):
                count = message.get_number_of_recipients()
                for i in range(count):
                    recipient = message.get_recipient(i)
                    # Try to get recipient type
                    try:
                        rtype = recipient.get_recipient_type() if hasattr(recipient, "get_recipient_type") else 1
                    except Exception:
                        rtype = 1  # Default to TO

                    type_match = (
                        (recipient_type == "to" and rtype == 1) or
                        (recipient_type == "cc" and rtype == 2) or
                        (recipient_type == "bcc" and rtype == 3)
                    )

                    if type_match:
                        email = None
                        if hasattr(recipient, "get_email_address"):
                            try:
                                email = recipient.get_email_address()
                            except Exception:
                                pass
                        if not email and hasattr(recipient, "get_display_name"):
                            try:
                                name = recipient.get_display_name()
                                if name and "@" in name:
                                    email = name
                            except Exception:
                                pass
                        if email:
                            recipients.append(email)
        except Exception:
            pass

        # Fallback to headers if no recipients found
        if not recipients:
            headers = self._extract_headers(message)
            header_key = recipient_type.lower()
            header_value = headers.get(header_key, "")
            if header_value:
                # Parse comma-separated list
                for addr in header_value.split(","):
                    addr = addr.strip()
                    if "<" in addr and ">" in addr:
                        email = addr[addr.index("<") + 1 : addr.index(">")]
                        recipients.append(email)
                    elif "@" in addr:
                        recipients.append(addr)

        return recipients

    def _extract_headers(self, message) -> dict[str, str]:
        """Extract email headers."""
        headers = {}

        try:
            transport_headers = message.get_transport_headers()
            if transport_headers:
                if isinstance(transport_headers, bytes):
                    transport_headers = transport_headers.decode("utf-8", errors="replace")

                for line in transport_headers.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        headers[key.strip().lower()] = value.strip()
        except Exception:
            pass

        return headers

    def _parse_date(self, date_value) -> datetime | None:
        """Parse date from various formats."""
        if date_value is None:
            return None

        if isinstance(date_value, datetime):
            return date_value

        try:
            # Handle timestamp
            if isinstance(date_value, (int, float)):
                return datetime.fromtimestamp(date_value)
        except Exception:
            pass

        return None

    def _parse_references(self, references_str: str) -> list[str]:
        """Parse References header into list of message IDs."""
        if not references_str:
            return []

        # References are space-separated message IDs
        refs = []
        for ref in references_str.split():
            ref = ref.strip()
            if ref.startswith("<") and ref.endswith(">"):
                refs.append(ref)
            elif ref:
                refs.append(f"<{ref}>")

        return refs

    def _generate_thread_id(self, message, headers: dict[str, str]) -> str | None:
        """Generate or extract thread ID."""
        # Try to get conversation index
        try:
            conv_index = message.get_conversation_index()
            if conv_index:
                return hashlib.md5(conv_index).hexdigest()[:16]
        except Exception:
            pass

        # Fall back to References header
        references = headers.get("references", "")
        if references:
            first_ref = references.split()[0] if references.split() else ""
            if first_ref:
                return hashlib.md5(first_ref.encode()).hexdigest()[:16]

        # Fall back to In-Reply-To
        in_reply_to = headers.get("in-reply-to", "")
        if in_reply_to:
            return hashlib.md5(in_reply_to.encode()).hexdigest()[:16]

        return None

    def _generate_message_id(
        self,
        internet_message_id: str,
        subject: str,
        sender: str,
        sent_date: datetime | None,
    ) -> str:
        """Generate unique message ID."""
        if internet_message_id:
            return hashlib.sha256(internet_message_id.encode()).hexdigest()[:32]

        # Generate from content
        date_str = sent_date.isoformat() if sent_date else ""
        content = f"{subject}{sender}{date_str}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _extract_attachments(
        self,
        message,
        max_size: int,
    ) -> list[ExtractedAttachment]:
        """Extract attachments from a message."""
        attachments = []

        try:
            num_attachments = message.get_number_of_attachments()
        except Exception as e:
            # Some messages have corrupted attachment metadata
            logger.debug(f"Cannot get attachment count: {e}")
            return attachments

        for i in range(num_attachments):
            try:
                attachment = message.get_attachment(i)

                # Get attachment filename - try multiple methods for pypff compatibility
                filename = None
                for attr in ['get_name', 'get_long_filename', 'get_short_filename', 'name', 'filename']:
                    try:
                        if hasattr(attachment, attr):
                            getter = getattr(attachment, attr)
                            filename = getter() if callable(getter) else getter
                            if filename:
                                break
                    except Exception:
                        continue

                if not filename:
                    filename = f"attachment_{i}"

                # Try to get size - try multiple methods
                size = 0
                for size_attr in ['get_size', 'size']:
                    try:
                        if hasattr(attachment, size_attr):
                            getter = getattr(attachment, size_attr)
                            size = getter() if callable(getter) else getter
                            if size and size > 0:
                                break
                    except Exception:
                        continue

                if size > max_size:
                    logger.warning(
                        f"Skipping large attachment {filename} ({size} bytes)"
                    )
                    continue

                # Get content - try multiple methods
                content = None
                try:
                    if hasattr(attachment, 'read_buffer'):
                        content = attachment.read_buffer(size if size > 0 else 1024 * 1024)
                    elif hasattr(attachment, 'get_data'):
                        content = attachment.get_data()
                except Exception as e:
                    logger.debug(f"Cannot read attachment content: {e}")
                    continue

                if content is None:
                    continue

                # Calculate hashes
                md5_hash = hashlib.md5(content).hexdigest()
                sha256_hash = hashlib.sha256(content).hexdigest()

                # Determine content type
                content_type = self._guess_content_type(filename)

                attachments.append(
                    ExtractedAttachment(
                        filename=filename,
                        content_type=content_type,
                        size_bytes=len(content),
                        content=content,
                        md5_hash=md5_hash,
                        sha256_hash=sha256_hash,
                    )
                )

            except Exception as e:
                logger.debug(f"Error extracting attachment {i}: {e}")
                continue

        return attachments

    def _guess_content_type(self, filename: str) -> str:
        """Guess content type from filename."""
        import mimetypes

        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"

    def _extract_text_from_html(self, html_content: str) -> str:
        """
        Extract plain text from HTML content.

        Uses BeautifulSoup if available, otherwise falls back to regex-based extraction.

        Args:
            html_content: HTML content string

        Returns:
            Extracted plain text
        """
        if not html_content:
            return ""

        try:
            # Try using BeautifulSoup for better HTML parsing
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "head", "meta", "link"]):
                element.decompose()

            # Get text and clean it up
            text = soup.get_text(separator="\n")

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            # Break multi-headlines into a line each
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            # Drop blank lines
            text = "\n".join(chunk for chunk in chunks if chunk)

            return text

        except ImportError:
            # Fallback to regex-based extraction
            import re

            # Remove script and style blocks
            text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

            # Remove HTML tags
            text = re.sub(r"<[^>]+>", " ", text)

            # Decode HTML entities
            import html
            text = html.unescape(text)

            # Clean up whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Convert multiple spaces to newlines for readability
            text = re.sub(r"  +", "\n", text)

            return text

        except Exception as e:
            logger.warning(f"Failed to extract text from HTML: {e}")
            return ""


def create_pst_processor(pst_path: str | Path) -> PSTProcessor:
    """Factory function to create PST processor."""
    return PSTProcessor(pst_path)
