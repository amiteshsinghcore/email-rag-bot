"""
Custom LLM Provider

Implementation for custom/self-hosted LLM endpoints.
Supports OpenAI-compatible APIs (like LM Studio, Ollama, vLLM, etc.)
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


class CustomProvider(BaseLLMProvider):
    """
    Custom LLM provider implementation.

    Supports any OpenAI-compatible API endpoint, including:
    - LM Studio
    - Ollama
    - vLLM
    - Text Generation Inference (TGI)
    - LocalAI
    - Any OpenAI-compatible server
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize custom provider.

        Args:
            api_key: API key (may not be required for local models)
            model: Model identifier
            base_url: Base URL for the custom endpoint
            **kwargs: Additional configuration
        """
        api_key = api_key or settings.custom_llm_api_key or "not-required"
        # Don't use "default" as fallback - it's not a valid model name for most providers
        resolved_model = model if model and model != "default" else settings.custom_llm_model
        if not resolved_model:
            raise LLMProviderError(
                "Custom LLM model not configured. Set CUSTOM_LLM_MODEL environment variable or configure the model in LLM settings.",
                provider=LLMProvider.CUSTOM,
            )
        self.base_url = base_url or settings.custom_llm_base_url
        super().__init__(api_key=api_key, model=resolved_model, **kwargs)
        self._async_client: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.CUSTOM

    @property
    def default_model(self) -> str:
        return "default"

    @property
    def supported_models(self) -> list[str]:
        # Custom providers can have any model
        return []

    def _get_async_client(self) -> Any:
        """Get or create async client for custom endpoint."""
        if not self.base_url:
            raise LLMProviderError(
                "Custom LLM base URL not configured",
                provider=self.provider_name,
            )

        if self._async_client is None:
            try:
                from openai import AsyncOpenAI

                self._async_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
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
        """Generate a response using custom endpoint."""
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
                    "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                    "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                    "total_tokens": getattr(response.usage, "total_tokens", 0),
                }

            return LLMResponse(
                content=choice.message.content or "",
                model=getattr(response, "model", self.model),
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
        """Generate a streaming response using custom endpoint."""
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
        """Handle custom endpoint errors."""
        error_str = str(error).lower()

        # Connection errors
        if "connect" in error_str or "refused" in error_str:
            raise LLMProviderError(
                f"Cannot connect to custom LLM at {self.base_url}: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "rate_limit" in error_str or "429" in error_str:
            raise RateLimitError(
                f"Custom LLM rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context" in error_str or "too long" in error_str or "token" in error_str:
            raise ContextLengthExceededError(
                f"Custom LLM context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "authentication" in error_str or "api_key" in error_str or "401" in error_str:
            raise APIKeyMissingError(
                f"Custom LLM authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        logger.error(f"Custom LLM error: {error}")
        raise LLMProviderError(
            f"Custom LLM error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )

    async def check_health(self) -> bool:
        """Check if the custom endpoint is healthy."""
        try:
            client = self._get_async_client()
            # Try to list models - most OpenAI-compatible APIs support this
            await client.models.list()
            return True
        except Exception as e:
            logger.warning(f"Custom LLM health check failed: {e}")
            return False

    @classmethod
    async def fetch_available_models(
        cls,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> list[str]:
        """
        Fetch available models from the custom endpoint.

        Args:
            base_url: Base URL for the custom endpoint
            api_key: API key for authentication

        Returns:
            List of available model IDs
        """
        resolved_base_url = base_url or settings.custom_llm_base_url
        resolved_api_key = api_key or settings.custom_llm_api_key or "not-required"

        if not resolved_base_url:
            logger.warning("Custom LLM base URL not configured, cannot fetch models")
            return []

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
            )

            models_response = await client.models.list()
            model_ids = [model.id for model in models_response.data]
            logger.info(f"Fetched {len(model_ids)} models from custom endpoint: {model_ids}")
            return sorted(model_ids)

        except ImportError:
            logger.error("openai package not installed")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch models from custom endpoint: {e}")
            return []
