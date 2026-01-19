"""
LLM Provider Factory

Factory for creating LLM provider instances.
"""

from functools import lru_cache
from typing import Any

from loguru import logger

from app.config import settings
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.base import (
    BaseLLMProvider,
    LLMProvider,
    LLMProviderError,
)
from app.services.llm.cerebras_provider import CerebrasProvider
from app.services.llm.custom_provider import CustomProvider
from app.services.llm.google_provider import GoogleProvider
from app.services.llm.groq_provider import GroqProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.xai_provider import XAIProvider


class LLMFactory:
    """
    Factory for creating and managing LLM provider instances.

    Supports dynamic provider selection and caching.
    """

    _providers: dict[str, type[BaseLLMProvider]] = {
        LLMProvider.OPENAI.value: OpenAIProvider,
        LLMProvider.ANTHROPIC.value: AnthropicProvider,
        LLMProvider.GOOGLE.value: GoogleProvider,
        LLMProvider.XAI.value: XAIProvider,
        LLMProvider.GROQ.value: GroqProvider,
        LLMProvider.CEREBRAS.value: CerebrasProvider,
        LLMProvider.CUSTOM.value: CustomProvider,
    }

    _instances: dict[str, BaseLLMProvider] = {}

    @classmethod
    def get_provider(
        cls,
        provider: str | LLMProvider | None = None,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> BaseLLMProvider:
        """
        Get an LLM provider instance.

        Args:
            provider: Provider name or enum (defaults to settings.default_llm_provider)
            api_key: Optional API key override
            model: Optional model override
            **kwargs: Additional provider-specific configuration

        Returns:
            LLM provider instance

        Raises:
            LLMProviderError: If provider is not supported
        """
        # Determine provider
        if provider is None:
            provider = settings.default_llm_provider

        if isinstance(provider, LLMProvider):
            provider_key = provider.value
        else:
            provider_key = provider.lower()

        # Validate provider
        if provider_key not in cls._providers:
            raise LLMProviderError(
                f"Unknown LLM provider: {provider_key}. "
                f"Supported providers: {list(cls._providers.keys())}"
            )

        # Create cache key based on configuration
        cache_key = f"{provider_key}:{model or 'default'}:{api_key or 'default'}"

        # Return cached instance if exists and no overrides
        if cache_key in cls._instances and not kwargs:
            return cls._instances[cache_key]

        # Create new instance
        provider_class = cls._providers[provider_key]
        instance = provider_class(api_key=api_key, model=model, **kwargs)

        # Cache the instance
        if not kwargs:  # Only cache if no custom kwargs
            cls._instances[cache_key] = instance

        logger.debug(f"Created LLM provider: {provider_key} with model {instance.model}")
        return instance

    # Display names for providers
    _display_names: dict[str, str] = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "xai": "xAI",
        "groq": "Groq",
        "cerebras": "Cerebras",
        "custom": "Custom",
    }

    @classmethod
    def get_available_providers(cls) -> list[dict[str, Any]]:
        """
        Get list of available providers with their configuration status.

        Returns:
            List of provider info dictionaries matching frontend LLMProvider interface
        """
        providers = []

        for provider_key, provider_class in cls._providers.items():
            # Create temporary instance to check configuration
            try:
                instance = provider_class()
                is_configured = instance.validate_api_key()
                models = instance.supported_models
                default_model = instance.model
            except Exception:
                is_configured = False
                models = []
                default_model = ""

            providers.append(
                {
                    "name": provider_key,
                    "display_name": cls._display_names.get(provider_key, provider_key.title()),
                    "is_available": is_configured,
                    "models": models,
                    "default_model": default_model,
                }
            )

        return providers

    @classmethod
    def _get_models_for_provider(cls, provider_key: str) -> list[str]:
        """Get supported models for a provider."""
        provider_class = cls._providers.get(provider_key)
        if provider_class:
            try:
                instance = provider_class()
                return instance.supported_models
            except Exception:
                pass
        return []

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached provider instances."""
        cls._instances.clear()
        logger.debug("LLM provider cache cleared")

    @classmethod
    def register_provider(
        cls,
        name: str,
        provider_class: type[BaseLLMProvider],
    ) -> None:
        """
        Register a custom provider class.

        Args:
            name: Provider name
            provider_class: Provider class implementing BaseLLMProvider
        """
        cls._providers[name.lower()] = provider_class
        logger.info(f"Registered custom LLM provider: {name}")


@lru_cache
def get_llm_provider(
    provider: str | None = None,
    model: str | None = None,
) -> BaseLLMProvider:
    """
    Get an LLM provider instance (cached).

    Convenience function for getting the default or specified provider.

    Args:
        provider: Provider name (optional)
        model: Model name (optional)

    Returns:
        LLM provider instance
    """
    return LLMFactory.get_provider(provider=provider, model=model)


# Default provider instance
def get_default_llm() -> BaseLLMProvider:
    """Get the default LLM provider based on settings."""
    return LLMFactory.get_provider()
