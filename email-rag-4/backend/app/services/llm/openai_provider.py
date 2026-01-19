"""
OpenAI LLM Provider

Implementation for OpenAI's GPT models.
"""

from typing import Any, AsyncIterator

from loguru import logger

from app.config import settings
from app.services.llm.base import (
    APIKeyMissingError,
    BaseLLMProvider,
    ContextLengthExceededError,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    Message,
    RateLimitError,
    StreamChunk,
)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI LLM provider implementation.

    Supports GPT-4, GPT-4 Turbo, and GPT-3.5 Turbo models.
    """

    SUPPORTED_MODELS = [
        "gpt-4-turbo-preview",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-4-0125-preview",
        "gpt-4-1106-preview",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-0125",
        "gpt-3.5-turbo-1106",
        "gpt-4o",
        "gpt-4o-mini",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize OpenAI provider."""
        api_key = api_key or settings.openai_api_key
        model = model or settings.openai_model
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._client: Any = None
        self._async_client: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.OPENAI

    @property
    def default_model(self) -> str:
        return "gpt-4-turbo-preview"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS

    def _get_async_client(self) -> Any:
        """Get or create async OpenAI client."""
        if not self.api_key:
            raise APIKeyMissingError(
                "OpenAI API key not configured",
                provider=self.provider_name,
            )

        if self._async_client is None:
            try:
                from openai import AsyncOpenAI

                self._async_client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise LLMProviderError(
                    "openai package not installed. Run: pip install openai",
                    provider=self.provider_name,
                )

        return self._async_client

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using OpenAI."""
        client = self._get_async_client()
        converted_messages = self._convert_messages(messages)

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=converted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            choice = response.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
                finish_reason=choice.finish_reason,
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

        except Exception as e:
            self._handle_error(e)

    async def generate_stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> AsyncIterator[StreamChunk]:
        """Generate a streaming response using OpenAI."""
        client = self._get_async_client()
        converted_messages = self._convert_messages(messages)

        try:
            stream = await client.chat.completions.create(
                model=self.model,
                messages=converted_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    delta = choice.delta

                    if delta.content:
                        yield StreamChunk(
                            content=delta.content,
                            is_final=choice.finish_reason is not None,
                            finish_reason=choice.finish_reason,
                        )
                    elif choice.finish_reason:
                        yield StreamChunk(
                            content="",
                            is_final=True,
                            finish_reason=choice.finish_reason,
                        )

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception) -> None:
        """Handle OpenAI-specific errors."""
        error_str = str(error).lower()

        if "rate_limit" in error_str or "429" in error_str:
            raise RateLimitError(
                f"OpenAI rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context_length" in error_str or "maximum context" in error_str:
            raise ContextLengthExceededError(
                f"OpenAI context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "invalid_api_key" in error_str or "authentication" in error_str:
            raise APIKeyMissingError(
                f"OpenAI authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        logger.error(f"OpenAI error: {error}")
        raise LLMProviderError(
            f"OpenAI error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )
