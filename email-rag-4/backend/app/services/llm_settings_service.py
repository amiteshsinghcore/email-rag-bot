"""
LLM Settings Service

Service for managing LLM provider configuration.
"""

import uuid
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMSettings


class LLMSettingsService:
    """Service for managing LLM provider settings."""

    VALID_PROVIDERS = [
        "openai",
        "anthropic",
        "google",
        "xai",
        "groq",
        "cerebras",
        "custom",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_settings(self, user_id: str | None = None) -> list[LLMSettings]:
        """
        Get all LLM settings.

        If user_id is provided, returns user-specific settings merged with system settings.
        Otherwise returns system-wide settings.
        """
        if user_id:
            # Get both system and user settings
            stmt = select(LLMSettings).where(
                (LLMSettings.user_id == None) | (LLMSettings.user_id == user_id)
            ).order_by(LLMSettings.provider)
        else:
            # Get only system settings
            stmt = select(LLMSettings).where(
                LLMSettings.user_id == None
            ).order_by(LLMSettings.provider)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_settings_by_provider(
        self,
        provider: str,
        user_id: str | None = None,
    ) -> LLMSettings | None:
        """
        Get settings for a specific provider.

        User settings take precedence over system settings.
        """
        if user_id:
            # Try user-specific first
            stmt = select(LLMSettings).where(
                and_(
                    LLMSettings.provider == provider,
                    LLMSettings.user_id == user_id,
                )
            )
            result = await self.db.execute(stmt)
            settings = result.scalar_one_or_none()
            if settings:
                return settings

        # Fall back to system settings
        stmt = select(LLMSettings).where(
            and_(
                LLMSettings.provider == provider,
                LLMSettings.user_id == None,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_or_update_settings(
        self,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        is_enabled: bool = True,
        is_default: bool = False,
        user_id: str | None = None,
    ) -> LLMSettings:
        """
        Create or update LLM settings for a provider.

        Args:
            provider: Provider identifier
            api_key: API key (None to keep existing, empty string to clear)
            model: Model name
            base_url: Base URL for custom endpoints
            is_enabled: Whether provider is enabled
            is_default: Whether this is the default provider
            user_id: User ID for user-specific settings (None for system-wide)
        """
        if provider not in self.VALID_PROVIDERS:
            raise ValueError(f"Invalid provider: {provider}")

        # Check if settings exist
        existing = await self.get_settings_by_provider(provider, user_id)

        if existing and (existing.user_id == user_id):
            # Update existing settings
            if api_key is not None:
                existing.api_key = api_key if api_key else None
            if model is not None:
                existing.model = model if model else None
            if base_url is not None:
                existing.base_url = base_url if base_url else None
            existing.is_enabled = is_enabled
            existing.is_default = is_default
            existing.updated_at = datetime.utcnow()

            # If setting as default, clear default on other providers
            if is_default:
                await self._clear_other_defaults(provider, user_id)

            await self.db.commit()
            await self.db.refresh(existing)
            logger.info(f"Updated LLM settings for provider: {provider}")
            return existing
        else:
            # Create new settings
            new_settings = LLMSettings(
                id=str(uuid.uuid4()),
                provider=provider,
                user_id=user_id,
                api_key=api_key if api_key else None,
                model=model if model else None,
                base_url=base_url if base_url else None,
                is_enabled=is_enabled,
                is_default=is_default,
            )

            # If setting as default, clear default on other providers
            if is_default:
                await self._clear_other_defaults(provider, user_id)

            self.db.add(new_settings)
            await self.db.commit()
            await self.db.refresh(new_settings)
            logger.info(f"Created LLM settings for provider: {provider}")
            return new_settings

    async def update_settings(
        self,
        settings_id: str,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        is_enabled: bool | None = None,
        is_default: bool | None = None,
    ) -> LLMSettings | None:
        """
        Update existing LLM settings by ID.
        """
        stmt = select(LLMSettings).where(LLMSettings.id == settings_id)
        result = await self.db.execute(stmt)
        settings = result.scalar_one_or_none()

        if not settings:
            return None

        if api_key is not None:
            settings.api_key = api_key if api_key else None
        if model is not None:
            settings.model = model if model else None
        if base_url is not None:
            settings.base_url = base_url if base_url else None
        if is_enabled is not None:
            settings.is_enabled = is_enabled
        if is_default is not None:
            settings.is_default = is_default
            if is_default:
                await self._clear_other_defaults(settings.provider, settings.user_id)

        settings.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(settings)
        return settings

    async def delete_settings(self, settings_id: str) -> bool:
        """Delete LLM settings by ID."""
        stmt = select(LLMSettings).where(LLMSettings.id == settings_id)
        result = await self.db.execute(stmt)
        settings = result.scalar_one_or_none()

        if not settings:
            return False

        await self.db.delete(settings)
        await self.db.commit()
        return True

    async def set_default_provider(
        self,
        provider: str,
        user_id: str | None = None,
    ) -> bool:
        """Set a provider as the default."""
        settings = await self.get_settings_by_provider(provider, user_id)
        if not settings:
            return False

        # Clear other defaults
        await self._clear_other_defaults(provider, user_id)

        # Set this as default
        settings.is_default = True
        settings.updated_at = datetime.utcnow()
        await self.db.commit()
        return True

    async def get_default_provider(
        self,
        user_id: str | None = None,
    ) -> str | None:
        """Get the default provider name."""
        settings = await self.get_default_settings(user_id)
        return settings.provider if settings else None

    async def get_default_settings(
        self,
        user_id: str | None = None,
    ) -> LLMSettings | None:
        """Get the default provider settings object."""
        if user_id:
            # Check user default first
            stmt = select(LLMSettings).where(
                and_(
                    LLMSettings.user_id == user_id,
                    LLMSettings.is_default == True,
                )
            )
            result = await self.db.execute(stmt)
            settings = result.scalar_one_or_none()
            if settings:
                return settings

        # Fall back to system default
        stmt = select(LLMSettings).where(
            and_(
                LLMSettings.user_id == None,
                LLMSettings.is_default == True,
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_effective_settings(
        self,
        provider: str,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get effective settings for a provider (for use with LLM factory).

        Merges system and user settings, with user settings taking precedence.
        """
        system_settings = await self.get_settings_by_provider(provider, None)
        user_settings = None

        if user_id:
            stmt = select(LLMSettings).where(
                and_(
                    LLMSettings.provider == provider,
                    LLMSettings.user_id == user_id,
                )
            )
            result = await self.db.execute(stmt)
            user_settings = result.scalar_one_or_none()

        # Merge settings (user takes precedence)
        effective = {}

        if system_settings:
            if system_settings.api_key:
                effective["api_key"] = system_settings.api_key
            if system_settings.model:
                effective["model"] = system_settings.model
            if system_settings.base_url:
                effective["base_url"] = system_settings.base_url

        if user_settings:
            if user_settings.api_key:
                effective["api_key"] = user_settings.api_key
            if user_settings.model:
                effective["model"] = user_settings.model
            if user_settings.base_url:
                effective["base_url"] = user_settings.base_url

        return effective if effective else None

    async def _clear_other_defaults(
        self,
        exclude_provider: str,
        user_id: str | None,
    ) -> None:
        """Clear the is_default flag on all other providers."""
        if user_id:
            stmt = (
                update(LLMSettings)
                .where(
                    and_(
                        LLMSettings.user_id == user_id,
                        LLMSettings.provider != exclude_provider,
                        LLMSettings.is_default == True,
                    )
                )
                .values(is_default=False, updated_at=datetime.utcnow())
            )
        else:
            stmt = (
                update(LLMSettings)
                .where(
                    and_(
                        LLMSettings.user_id == None,
                        LLMSettings.provider != exclude_provider,
                        LLMSettings.is_default == True,
                    )
                )
                .values(is_default=False, updated_at=datetime.utcnow())
            )
        await self.db.execute(stmt)


def get_llm_settings_service(db: AsyncSession) -> LLMSettingsService:
    """Factory function to create LLMSettingsService."""
    return LLMSettingsService(db)
