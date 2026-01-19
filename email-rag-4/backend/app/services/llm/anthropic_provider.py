"""
Anthropic LLM Provider

Implementation for Anthropic's Claude models.
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


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic LLM provider implementation.

    Supports Claude 3 (Opus, Sonnet, Haiku) and Claude 2 models.
    """

    SUPPORTED_MODELS = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20240620",
        "claude-3-5-sonnet-20241022",
        "claude-2.1",
        "claude-2.0",
        "claude-instant-1.2",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Anthropic provider."""
        api_key = api_key or settings.anthropic_api_key
        model = model or settings.anthropic_model
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._async_client: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    @property
    def default_model(self) -> str:
        return "claude-3-sonnet-20240229"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS

    def _get_async_client(self) -> Any:
        """Get or create async Anthropic client."""
        if not self.api_key:
            raise APIKeyMissingError(
                "Anthropic API key not configured",
                provider=self.provider_name,
            )

        if self._async_client is None:
            try:
                from anthropic import AsyncAnthropic

                self._async_client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise LLMProviderError(
                    "anthropic package not installed. Run: pip install anthropic",
                    provider=self.provider_name,
                )

        return self._async_client

    def _convert_messages_anthropic(
        self, messages: list[Message]
    ) -> tuple[str | None, list[dict[str, str]]]:
        """
        Convert messages to Anthropic format.

        Anthropic requires system message to be separate from conversation.

        Returns:
            Tuple of (system_message, conversation_messages)
        """
        system_message = None
        conversation = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation.append({"role": msg.role, "content": msg.content})

        return system_message, conversation

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using Anthropic."""
        client = self._get_async_client()
        system_message, conversation = self._convert_messages_anthropic(messages)

        try:
            response = await client.messages.create(
                model=self.model,
                messages=conversation,
                system=system_message or "",
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            # Extract content from response
            content = ""
            if response.content:
                content = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )

            return LLMResponse(
                content=content,
                model=response.model,
                provider=self.provider_name,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens
                    + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
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
        """Generate a streaming response using Anthropic."""
        client = self._get_async_client()
        system_message, conversation = self._convert_messages_anthropic(messages)

        try:
            async with client.messages.stream(
                model=self.model,
                messages=conversation,
                system=system_message or "",
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(
                        content=text,
                        is_final=False,
                    )

                # Final chunk
                yield StreamChunk(
                    content="",
                    is_final=True,
                    finish_reason="end_turn",
                )

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception) -> None:
        """Handle Anthropic-specific errors."""
        error_str = str(error).lower()

        if "rate_limit" in error_str or "429" in error_str:
            raise RateLimitError(
                f"Anthropic rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context_length" in error_str or "too long" in error_str:
            raise ContextLengthExceededError(
                f"Anthropic context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "authentication" in error_str or "api_key" in error_str or "401" in error_str:
            raise APIKeyMissingError(
                f"Anthropic authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        logger.error(f"Anthropic error: {error}")
        raise LLMProviderError(
            f"Anthropic error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )
