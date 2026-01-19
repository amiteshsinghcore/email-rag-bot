"""
Cerebras LLM Provider

Implementation for Cerebras AI inference API.
Cerebras offers extremely fast inference with their custom hardware.
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


class CerebrasProvider(BaseLLMProvider):
    """
    Cerebras LLM provider implementation.

    Cerebras provides extremely fast inference using their custom
    Wafer-Scale Engine hardware. They offer an OpenAI-compatible API.

    Supported models:
    - llama3.1-8b: Fast, efficient for most tasks
    - llama3.1-70b: More capable, still very fast
    - llama-3.3-70b: Latest Llama model
    """

    # Cerebras API base URL
    BASE_URL = "https://api.cerebras.ai/v1"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize Cerebras provider.

        Args:
            api_key: Cerebras API key
            model: Model identifier
            **kwargs: Additional configuration
        """
        api_key = api_key or settings.cerebras_api_key
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._async_client: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.CEREBRAS

    @property
    def default_model(self) -> str:
        return settings.cerebras_model or "llama-3.3-70b"

    @property
    def supported_models(self) -> list[str]:
        return [
            "llama-3.3-70b",
            "llama3.1-70b",
            "llama3.1-8b",
        ]

    def _get_async_client(self) -> Any:
        """Get or create async client for Cerebras API."""
        if not self.api_key:
            raise APIKeyMissingError(
                "Cerebras API key not configured. Set CEREBRAS_API_KEY environment variable.",
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
        """Generate a response using Cerebras API."""
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
        """Generate a streaming response using Cerebras API."""
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

                    if hasattr(delta, "content") and delta.content:
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
        """Handle Cerebras API errors."""
        error_str = str(error).lower()

        if "401" in error_str or "unauthorized" in error_str or "invalid api key" in error_str:
            raise APIKeyMissingError(
                f"Cerebras API authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        if "429" in error_str or "rate_limit" in error_str or "too many requests" in error_str:
            raise RateLimitError(
                f"Cerebras API rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context" in error_str or "too long" in error_str or "token" in error_str:
            raise ContextLengthExceededError(
                f"Cerebras context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        logger.error(f"Cerebras API error: {error}")
        raise LLMProviderError(
            f"Cerebras API error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )
