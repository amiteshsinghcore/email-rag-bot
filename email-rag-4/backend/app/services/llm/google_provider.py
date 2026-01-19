"""
Google Gemini LLM Provider

Implementation for Google's Gemini models.
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


class GoogleProvider(BaseLLMProvider):
    """
    Google Gemini LLM provider implementation.

    Supports Gemini Pro and Gemini Ultra models.
    """

    SUPPORTED_MODELS = [
        "gemini-pro",
        "gemini-1.0-pro",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-ultra",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize Google provider."""
        api_key = api_key or settings.google_api_key
        model = model or settings.google_model
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._model_instance: Any = None

    @property
    def provider_name(self) -> LLMProvider:
        return LLMProvider.GOOGLE

    @property
    def default_model(self) -> str:
        return "gemini-pro"

    @property
    def supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS

    def _get_model(self) -> Any:
        """Get or create Google Generative AI model."""
        if not self.api_key:
            raise APIKeyMissingError(
                "Google API key not configured",
                provider=self.provider_name,
            )

        if self._model_instance is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._model_instance = genai.GenerativeModel(self.model)
            except ImportError:
                raise LLMProviderError(
                    "google-generativeai package not installed. Run: pip install google-generativeai",
                    provider=self.provider_name,
                )

        return self._model_instance

    def _convert_messages_google(self, messages: list[Message]) -> tuple[str | None, list[dict]]:
        """
        Convert messages to Google Gemini format.

        Gemini uses 'user' and 'model' roles, and system instructions separately.

        Returns:
            Tuple of (system_instruction, conversation_history)
        """
        system_instruction = None
        history = []

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            elif msg.role == "assistant":
                history.append({"role": "model", "parts": [msg.content]})
            else:
                history.append({"role": "user", "parts": [msg.content]})

        return system_instruction, history

    async def generate(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate a response using Google Gemini."""
        model = self._get_model()
        system_instruction, history = self._convert_messages_google(messages)

        try:
            # Configure generation settings
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                **kwargs,
            }

            # Start chat with history (excluding the last message which we'll send)
            chat = model.start_chat(history=history[:-1] if len(history) > 1 else [])

            # Send the last message
            last_message = history[-1]["parts"][0] if history else ""
            if system_instruction:
                last_message = f"{system_instruction}\n\n{last_message}"

            response = await chat.send_message_async(
                last_message,
                generation_config=generation_config,
            )

            # Calculate token usage (Gemini provides this differently)
            usage = {}
            if hasattr(response, "usage_metadata"):
                usage = {
                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                    "completion_tokens": getattr(
                        response.usage_metadata, "candidates_token_count", 0
                    ),
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
                }

            return LLMResponse(
                content=response.text,
                model=self.model,
                provider=self.provider_name,
                usage=usage,
                finish_reason="stop",
                raw_response=None,  # Gemini response not easily serializable
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
        """Generate a streaming response using Google Gemini."""
        model = self._get_model()
        system_instruction, history = self._convert_messages_google(messages)

        try:
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
                **kwargs,
            }

            chat = model.start_chat(history=history[:-1] if len(history) > 1 else [])

            last_message = history[-1]["parts"][0] if history else ""
            if system_instruction:
                last_message = f"{system_instruction}\n\n{last_message}"

            response = await chat.send_message_async(
                last_message,
                generation_config=generation_config,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield StreamChunk(
                        content=chunk.text,
                        is_final=False,
                    )

            yield StreamChunk(
                content="",
                is_final=True,
                finish_reason="stop",
            )

        except Exception as e:
            self._handle_error(e)

    def _handle_error(self, error: Exception) -> None:
        """Handle Google-specific errors."""
        error_str = str(error).lower()

        if "quota" in error_str or "rate" in error_str or "429" in error_str:
            raise RateLimitError(
                f"Google rate limit exceeded: {error}",
                provider=self.provider_name,
                status_code=429,
                raw_error=error,
            )

        if "context" in error_str or "too long" in error_str or "token" in error_str:
            raise ContextLengthExceededError(
                f"Google context length exceeded: {error}",
                provider=self.provider_name,
                raw_error=error,
            )

        if "api_key" in error_str or "authentication" in error_str or "401" in error_str:
            raise APIKeyMissingError(
                f"Google authentication failed: {error}",
                provider=self.provider_name,
                status_code=401,
                raw_error=error,
            )

        logger.error(f"Google Gemini error: {error}")
        raise LLMProviderError(
            f"Google Gemini error: {error}",
            provider=self.provider_name,
            raw_error=error,
        )
