"""
Search Schemas

Pydantic schemas for search request/response validation.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class SearchFiltersSchema(BaseModel):
    """Filters for search requests."""

    pst_file_ids: list[str] | None = Field(
        default=None,
        description="Filter by PST file IDs",
    )
    sender_emails: list[str] | None = Field(
        default=None,
        description="Filter by sender email addresses",
    )
    recipient_emails: list[str] | None = Field(
        default=None,
        description="Filter by recipient email addresses",
    )
    date_from: datetime | None = Field(
        default=None,
        description="Filter emails from this date",
    )
    date_to: datetime | None = Field(
        default=None,
        description="Filter emails until this date",
    )
    has_attachments: bool | None = Field(
        default=None,
        description="Filter by attachment presence",
    )
    folder_paths: list[str] | None = Field(
        default=None,
        description="Filter by folder paths (prefix match)",
    )
    importance: str | None = Field(
        default=None,
        description="Filter by importance level",
    )
    attachment_types: list[str] | None = Field(
        default=None,
        description="Filter by attachment file types",
    )


class SearchRequest(BaseModel):
    """Search request schema."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query text",
    )
    filters: SearchFiltersSchema | None = Field(
        default=None,
        description="Optional filters to narrow results",
    )
    page: int = Field(
        default=1,
        ge=1,
        description="Page number (1-indexed)",
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Results per page",
    )
    search_type: str = Field(
        default="hybrid",
        description="Search type: 'semantic', 'fulltext', or 'hybrid'",
    )
    include_attachments: bool = Field(
        default=True,
        description="Include attachment content in search",
    )


class AdvancedSearchRequest(BaseModel):
    """Advanced search with filters."""

    filters: SearchFiltersSchema = Field(
        ...,
        description="Search filters",
    )
    query: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional search query",
    )
    page: int = Field(
        default=1,
        ge=1,
    )
    page_size: int = Field(
        default=20,
        ge=1,
        le=100,
    )
    sort_by: str = Field(
        default="sent_date",
        description="Field to sort by",
    )
    sort_order: str = Field(
        default="desc",
        description="Sort order: 'asc' or 'desc'",
    )


class SearchResultSchema(BaseModel):
    """Single search result."""

    email_id: str
    subject: str | None
    sender_email: str | None
    sender_name: str | None
    sent_date: datetime | None
    snippet: str | None
    score: float
    match_type: str
    highlights: list[str] = []
    has_attachments: bool = False
    attachment_count: int = 0
    folder_path: str | None = None
    pst_file_id: str | None = None


class ProcessedQueryInfoSchema(BaseModel):
    """Information about query processing."""

    original_query: str
    query_type: str
    keywords: list[str] = []
    entities: list[str] = []
    time_range: dict[str, str | None] | None = None


class SearchResponse(BaseModel):
    """Search response schema."""

    results: list[SearchResultSchema]
    total_count: int
    query: str
    processed_query: ProcessedQueryInfoSchema | None = None
    search_time_ms: float
    page: int
    page_size: int
    has_more: bool


class SuggestionRequest(BaseModel):
    """Search suggestion request."""

    partial_query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Partial query for suggestions",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum suggestions to return",
    )


class SuggestionsResponse(BaseModel):
    """Search suggestions response."""

    suggestions: list[str]
    query: str


class FacetValue(BaseModel):
    """Single facet value with count."""

    value: str
    count: int


class FacetsResponse(BaseModel):
    """Search facets response."""

    senders: list[FacetValue] = []
    folders: list[FacetValue] = []
    date_ranges: list[FacetValue] = []
    importance: list[FacetValue] = []
