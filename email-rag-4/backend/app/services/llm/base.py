"""
Base LLM Provider Interface

Abstract base class for all LLM providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    XAI = "xai"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    CUSTOM = "custom"


@dataclass
class Message:
    """Represents a chat message."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str
    model: str
    provider: LLMProvider
    usage: dict[str, int] = field(default_factory=dict)
    finish_reason: str | None = None
    raw_response: dict[str, Any] | None = None


@dataclass
class StreamChunk:
    """A chunk from a streaming response."""

    content: str
    is_final: bool = False
    finish_reason: str | None = None


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers must implement this interface.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the LLM provider.

        Args:
            api_key: API key for the provider
            model: Model identifier to use
            **kwargs: Additional provider-specific configuration
        """
        self.api_key = api_key
        self.model = model or self.default_model
        self.config = kwargs

    @property
    @abstractmethod
    def provider_name(self) -> LLMProvider:
        """Get the provider identifier."""
        ...

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Get the default model for this provider."""
        ...

    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        """Get list of supported models for this provider."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated content
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (0.0-2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Yields:
            StreamChunk objects with content fragments
        """
        ...

    def validate_api_key(self) -> bool:
        """Check if the API key is configured."""
        return bool(self.api_key)

    def _convert_messages(self, messages: list[Message]) -> list[dict[str, str]]:
        """Convert Message objects to provider-specific format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    def __init__(
        self,
        message: str,
        provider: LLMProvider | None = None,
        status_code: int | None = None,
        raw_error: Any = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.raw_error = raw_error


class APIKeyMissingError(LLMProviderError):
    """Raised when API key is not configured."""

    pass


class RateLimitError(LLMProviderError):
    """Raised when rate limit is exceeded."""

    pass


class ModelNotFoundError(LLMProviderError):
    """Raised when the requested model is not available."""

    pass


class ContextLengthExceededError(LLMProviderError):
    """Raised when the context length is exceeded."""

    pass
