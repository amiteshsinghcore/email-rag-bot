"""
LLM Settings Database Model

Stores LLM provider configuration settings.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class LLMSettings(Base, UUIDMixin, TimestampMixin):
    """
    LLM Provider Settings model.

    Stores API keys, models, and endpoints for LLM providers.
    Settings can be system-wide (user_id=None) or per-user.
    """

    __tablename__ = "llm_settings"
    __table_args__ = (
        UniqueConstraint("provider", "user_id", name="uq_llm_settings_provider_user"),
    )

    # Provider identifier (openai, anthropic, google, xai, groq, cerebras, custom)
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Optional user ID - None means system-wide setting
    user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        nullable=True,
        index=True,
    )

    # API Key (encrypted in production)
    api_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Model to use
    model: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Base URL (for custom providers or overrides)
    base_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    # Whether this provider is enabled
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Whether this is the default provider
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    def __repr__(self) -> str:
        return f"<LLMSettings(provider={self.provider}, user_id={self.user_id}, model={self.model})>"

    def to_dict(self) -> dict:
        """Convert to dictionary (hiding full API key)."""
        return {
            "id": str(self.id),
            "provider": self.provider,
            "user_id": str(self.user_id) if self.user_id else None,
            "api_key_set": bool(self.api_key),
            "api_key_preview": self._mask_api_key(),
            "model": self.model,
            "base_url": self.base_url,
            "is_enabled": self.is_enabled,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def _mask_api_key(self) -> str | None:
        """Return masked version of API key for display."""
        if not self.api_key:
            return None
        key = self.api_key
        if len(key) <= 8:
            return "*" * len(key)
        return key[:4] + "*" * (len(key) - 8) + key[-4:]
