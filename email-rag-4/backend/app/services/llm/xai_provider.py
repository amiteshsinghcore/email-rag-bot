"""
xAI Grok LLM Provider

Implementation for xAI's Grok models.
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


class XAIProvider(BaseLLMProvider):
    """
    xAI Grok LLM provider implementation.

    Uses OpenAI-compatible API for xAI's Grok models.
    """

    SUPPORTED_MODELS = [
        "grok-beta",
        "grok-2",
        "grok-2-mini",
    ]

    XAI_BASE_URL = "https://api.x.ai/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize xAI provider."""
        api_key = api_key or settings.xai_api_key
        model = model or settings.xai_model
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._async_client: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.XAI

    @property
    def default_model(self) -> str:
        return "grok-beta"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS

    def _get_async_client(self) -> Any:
        """Get or create async client using OpenAI SDK with xAI base URL."""
        if not self.api_key:
            raise APIKeyMissingError(
                "xAI API key not configured",
                provider=self.provider_name,
            )

        if self._async_client is None:
            try:
                from openai import AsyncOpenAI

                self._async_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.XAI_BASE_URL,
                )
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
        """Generate a response using xAI Grok."""
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
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            return LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                provider=self.provider_name,
                usage=usage,
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
        """Generate a streaming response using xAI Grok."""
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
        """Handle xAI-specific errors."""
        error_str = str(error).lower()

        if "rate_limit" in error_str or "429" in error_str:
            raise RateLimitError(
                f"xAI rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context_length" in error_str or "maximum context" in error_str:
            raise ContextLengthExceededError(
                f"xAI context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "invalid_api_key" in error_str or "authentication" in error_str or "401" in error_str:
            raise APIKeyMissingError(
                f"xAI authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        logger.error(f"xAI Grok error: {error}")
        raise LLMProviderError(
            f"xAI Grok error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )
