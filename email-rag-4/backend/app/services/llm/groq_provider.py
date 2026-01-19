"""
Groq LLM Provider

Implementation for Groq's fast inference API.
Groq uses an OpenAI-compatible API format.
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


class GroqProvider(BaseLLMProvider):
    """
    Groq LLM provider implementation.

    Supports Llama, Mixtral, and Gemma models with ultra-fast inference.
    Uses OpenAI-compatible API format.
    """

    SUPPORTED_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "gemma-7b-it",
    ]

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Groq provider."""
        api_key = api_key or settings.groq_api_key
        model = model or settings.groq_model
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._async_client: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.GROQ

    @property
    def default_model(self) -> str:
        return "llama-3.3-70b-versatile"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS

    def _get_async_client(self) -> Any:
        """Get or create async OpenAI-compatible client for Groq."""
        if not self.api_key:
            raise APIKeyMissingError(
                "Groq API key not configured",
                provider=self.provider_name,
            )

        if self._async_client is None:
            try:
                from openai import AsyncOpenAI

                self._async_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.BASE_URL,
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
        """Generate a response using Groq."""
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
        """Generate a streaming response using Groq."""
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
        """Handle Groq-specific errors."""
        error_str = str(error).lower()

        if "rate_limit" in error_str or "429" in error_str:
            raise RateLimitError(
                f"Groq rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context_length" in error_str or "maximum context" in error_str:
            raise ContextLengthExceededError(
                f"Groq context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "invalid_api_key" in error_str or "authentication" in error_str:
            raise APIKeyMissingError(
                f"Groq authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        logger.error(f"Groq error: {error}")
        raise LLMProviderError(
            f"Groq error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )
