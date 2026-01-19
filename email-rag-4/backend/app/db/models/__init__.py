"""
Database Models Package

Exports all SQLAlchemy models for the application.
"""

from app.db.models.attachment import Attachment
from app.db.models.email import Email, EmailImportance
from app.db.models.evidence import AuditLog, Evidence, EvidenceAction
from app.db.models.llm_settings import LLMSettings
from app.db.models.processing_task import ProcessingTask, TaskStatus
from app.db.models.user import User, UserRole

__all__ = [
    # User
    "User",
    "UserRole",
    # Email
    "Email",
    "EmailImportance",
    # Attachment
    "Attachment",
    # Processing Task
    "ProcessingTask",
    "TaskStatus",
    # Evidence & Audit
    "Evidence",
    "EvidenceAction",
    "AuditLog",
    # LLM Settings
    "LLMSettings",
]
