"""
User Database Model

Handles user accounts, authentication, and role-based access control.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.email import Email
    from app.db.models.processing_task import ProcessingTask


class UserRole(str, Enum):
    """User roles for RBAC."""

    ADMIN = "admin"
    INVESTIGATOR = "investigator"
    VIEWER = "viewer"


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """User account model."""

    __tablename__ = "users"

    # Authentication fields
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Profile fields
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Role and permissions
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UserRole.VIEWER.value,
        index=True,
    )

    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Security fields
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_ip: Mapped[str | None] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Password reset
    password_reset_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    password_reset_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Email verification
    verification_token: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Settings (JSON stored as text)
    settings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default="{}",
    )

    # Relationships
    processing_tasks: Mapped[list["ProcessingTask"]] = relationship(
        "ProcessingTask",
        back_populates="user",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN.value

    @property
    def is_investigator(self) -> bool:
        """Check if user has investigator role or higher."""
        return self.role in (UserRole.ADMIN.value, UserRole.INVESTIGATOR.value)

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until is None:
            return False
        return datetime.now(self.locked_until.tzinfo) < self.locked_until

    def get_rate_limit(self) -> int:
        """Get rate limit based on user role."""
        from app.config import settings

        if self.role == UserRole.ADMIN.value:
            return settings.rate_limit_admin
        elif self.role == UserRole.INVESTIGATOR.value:
            return settings.rate_limit_investigator
        return settings.rate_limit_standard
