"""
RAG Schemas

Pydantic schemas for RAG/Chat API requests and responses.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ===========================================
# Chat/Query Schemas
# ===========================================


class ChatMessageSchema(BaseModel):
    """A chat message in conversation history."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request for chat/query endpoint."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's question about the emails",
    )
    chat_history: list[ChatMessageSchema] | None = Field(
        default=None,
        description="Previous conversation messages",
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider to use (openai, anthropic, google, xai, custom)",
    )
    model: str | None = Field(
        default=None,
        description="Specific model to use",
    )
    pst_file_ids: list[str] | None = Field(
        default=None,
        description="Filter to specific PST files",
    )
    top_k: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Number of documents to retrieve",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="LLM temperature for response generation",
    )
    max_tokens: int = Field(
        default=4096,
        ge=100,
        le=16000,
        description="Maximum tokens to generate",
    )
    include_sources: bool = Field(
        default=True,
        description="Whether to include source citations",
    )
    stream: bool = Field(
        default=False,
        description="Whether to stream the response",
    )


class SourceSchema(BaseModel):
    """A source citation for a RAG response."""

    id: str = Field(..., description="Document chunk ID")
    type: str = Field(..., description="Source type: 'email' or 'attachment'")
    score: float = Field(..., description="Relevance score")
    email_id: str | None = Field(default=None, description="Email ID")
    subject: str | None = Field(default=None, description="Email subject")
    sender: str | None = Field(default=None, description="Email sender")
    date: str | None = Field(default=None, description="Email date")
    filename: str | None = Field(default=None, description="Attachment filename")


class ProcessedQuerySchema(BaseModel):
    """Information about how the query was processed."""

    original: str = Field(..., description="Original query text")
    type: str = Field(..., description="Detected query type")
    entities: list[str] = Field(default_factory=list, description="Extracted entities")
    keywords: list[str] = Field(default_factory=list, description="Extracted keywords")
    time_range: dict[str, str | None] | None = Field(
        default=None,
        description="Extracted time range",
    )


class ChatResponse(BaseModel):
    """Response from chat/query endpoint."""

    answer: str = Field(..., description="Generated answer")
    sources: list[SourceSchema] = Field(
        default_factory=list,
        description="Source citations",
    )
    query_type: str = Field(..., description="Detected query type")
    processed_query: ProcessedQuerySchema | None = Field(
        default=None,
        description="Query processing details",
    )
    model_used: str = Field(..., description="Model that generated the response")
    provider_used: str = Field(..., description="LLM provider used")
    total_tokens: int = Field(default=0, description="Total tokens used")


# ===========================================
# Summarization Schemas
# ===========================================


class SummarizeRequest(BaseModel):
    """Request for email summarization."""

    email_ids: list[str] | None = Field(
        default=None,
        description="Specific email IDs to summarize",
    )
    pst_file_ids: list[str] | None = Field(
        default=None,
        description="Filter to specific PST files",
    )
    topic: str | None = Field(
        default=None,
        max_length=500,
        description="Focus summary on specific topic",
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider to use",
    )
    model: str | None = Field(
        default=None,
        description="Specific model to use",
    )
    max_emails: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum emails to include",
    )


class SummarizeResponse(BaseModel):
    """Response from summarization endpoint."""

    summary: str = Field(..., description="Generated summary")
    sources: list[SourceSchema] = Field(
        default_factory=list,
        description="Source citations",
    )
    email_count: int = Field(..., description="Number of emails summarized")
    model_used: str = Field(..., description="Model used")
    provider_used: str = Field(..., description="Provider used")


# ===========================================
# Provider Schemas
# ===========================================


class LLMProviderInfo(BaseModel):
    """Information about an LLM provider."""

    name: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Display name")
    is_available: bool = Field(..., description="Whether provider is configured/available")
    models: list[str] = Field(
        default_factory=list,
        description="List of supported models",
    )
    default_model: str = Field("", description="Default model for this provider")


class ProvidersResponse(BaseModel):
    """Response listing available LLM providers."""

    providers: list[LLMProviderInfo] = Field(..., description="Available providers")
    default_provider: str = Field(..., description="Default provider")


# ===========================================
# Search Enhancement Schemas
# ===========================================


class SearchEnhanceRequest(BaseModel):
    """Request for query enhancement/suggestions."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Query to enhance",
    )


class SearchEnhanceResponse(BaseModel):
    """Response with enhanced query information."""

    original_query: str = Field(..., description="Original query")
    query_type: str = Field(..., description="Detected query type")
    suggestions: list[str] = Field(
        default_factory=list,
        description="Suggested alternative queries",
    )
    expanded_terms: list[str] = Field(
        default_factory=list,
        description="Expanded abbreviations",
    )
    entities: list[str] = Field(
        default_factory=list,
        description="Extracted entities",
    )
    time_range: dict[str, str | None] | None = Field(
        default=None,
        description="Extracted time range",
    )


# ===========================================
# Streaming Event Schemas
# ===========================================


class StreamEvent(BaseModel):
    """Event in streaming response."""

    event: str = Field(
        ...,
        description="Event type: 'start', 'chunk', 'sources', 'end', 'error'",
    )
    data: dict[str, Any] = Field(
        default_factory=dict,
        description="Event data",
    )


# ===========================================
# API Key Testing Schemas
# ===========================================


class TestApiKeyRequest(BaseModel):
    """Request to test an LLM API key."""

    provider: str = Field(
        ...,
        description="Provider to test (openai, anthropic, google, xai, groq, custom)",
    )
    api_key: str = Field(..., min_length=1, description="API key to test")
    model: str | None = Field(
        default=None,
        description="Optional model to test with",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for custom provider",
    )


class TestApiKeyResponse(BaseModel):
    """Response from API key test."""

    success: bool = Field(..., description="Whether the API key is valid")
    provider: str = Field(..., description="Provider tested")
    model: str | None = Field(default=None, description="Model tested")
    message: str = Field(..., description="Result message")
    error: str | None = Field(default=None, description="Error details if failed")


# ===========================================
# Error Schemas
# ===========================================


class RAGErrorResponse(BaseModel):
    """Error response for RAG endpoints."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type")
    provider: str | None = Field(default=None, description="Provider that failed")
    details: dict[str, Any] | None = Field(default=None, description="Additional details")


# ===========================================
# LLM Settings Schemas
# ===========================================


class LLMSettingsCreate(BaseModel):
    """Request to create/update LLM settings for a provider."""

    provider: str = Field(
        ...,
        description="Provider identifier (openai, anthropic, google, xai, groq, cerebras, custom)",
    )
    api_key: str | None = Field(
        default=None,
        description="API key for the provider",
    )
    model: str | None = Field(
        default=None,
        description="Default model to use",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for custom endpoints",
    )
    is_enabled: bool = Field(
        default=True,
        description="Whether this provider is enabled",
    )
    is_default: bool = Field(
        default=False,
        description="Whether this is the default provider",
    )


class LLMSettingsUpdate(BaseModel):
    """Request to update LLM settings."""

    api_key: str | None = Field(
        default=None,
        description="API key (set to empty string to clear)",
    )
    model: str | None = Field(
        default=None,
        description="Default model",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for custom endpoints",
    )
    is_enabled: bool | None = Field(
        default=None,
        description="Whether this provider is enabled",
    )
    is_default: bool | None = Field(
        default=None,
        description="Whether this is the default provider",
    )


class LLMSettingsResponse(BaseModel):
    """Response with LLM settings (API key masked)."""

    id: str = Field(..., description="Settings ID")
    provider: str = Field(..., description="Provider identifier")
    user_id: str | None = Field(default=None, description="User ID (null for system-wide)")
    api_key_set: bool = Field(..., description="Whether API key is configured")
    api_key_preview: str | None = Field(default=None, description="Masked API key preview")
    model: str | None = Field(default=None, description="Configured model")
    base_url: str | None = Field(default=None, description="Configured base URL")
    is_enabled: bool = Field(..., description="Whether provider is enabled")
    is_default: bool = Field(..., description="Whether this is the default provider")
    created_at: str | None = Field(default=None, description="Creation timestamp")
    updated_at: str | None = Field(default=None, description="Last update timestamp")


class AllLLMSettingsResponse(BaseModel):
    """Response with all LLM settings."""

    settings: list[LLMSettingsResponse] = Field(
        default_factory=list,
        description="List of all configured LLM settings",
    )
    default_provider: str | None = Field(
        default=None,
        description="Current default provider",
    )
