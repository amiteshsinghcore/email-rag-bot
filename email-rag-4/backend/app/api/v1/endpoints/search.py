"""
Search API Endpoints

Endpoints for searching emails using natural language and filters.
"""

from fastapi import APIRouter, HTTPException, status
from loguru import logger

from app.api.deps import CurrentUser
from app.schemas.search import (
    AdvancedSearchRequest,
    FacetsResponse,
    FacetValue,
    ProcessedQueryInfoSchema,
    SearchRequest,
    SearchResponse,
    SearchResultSchema,
    SuggestionRequest,
    SuggestionsResponse,
)
from app.services.search_service import SearchFilters, get_search_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "",
    response_model=SearchResponse,
    summary="Search emails",
    description="Search emails using natural language query with optional filters.",
)
async def search_emails(
    request: SearchRequest,
    current_user: CurrentUser,
) -> SearchResponse:
    """
    Search emails using natural language.

    Supports semantic search, full-text search, or hybrid mode.
    Returns ranked results with snippets and relevance scores.
    """
    search_service = get_search_service()

    try:
        # Convert schema filters to service filters
        filters = None
        if request.filters:
            filters = SearchFilters(
                pst_file_ids=request.filters.pst_file_ids,
                sender_emails=request.filters.sender_emails,
                recipient_emails=request.filters.recipient_emails,
                date_from=request.filters.date_from,
                date_to=request.filters.date_to,
                has_attachments=request.filters.has_attachments,
                folder_paths=request.filters.folder_paths,
                importance=request.filters.importance,
                attachment_types=request.filters.attachment_types,
            )

        result = await search_service.search(
            query=request.query,
            filters=filters,
            page=request.page,
            page_size=request.page_size,
            search_type=request.search_type,
            include_attachments=request.include_attachments,
        )

        # Convert to response schema
        results = [
            SearchResultSchema(
                email_id=r.email_id,
                subject=r.subject,
                sender_email=r.sender_email,
                sender_name=r.sender_name,
                sent_date=r.sent_date,
                snippet=r.snippet,
                score=r.score,
                match_type=r.match_type,
                highlights=r.highlights,
                has_attachments=r.has_attachments,
                attachment_count=r.attachment_count,
                folder_path=r.folder_path,
                pst_file_id=r.pst_file_id,
            )
            for r in result.results
        ]

        processed_query = None
        if result.processed_query:
            time_range = None
            if result.processed_query.time_range:
                time_range = {
                    "start": result.processed_query.time_range.start.isoformat()
                    if result.processed_query.time_range.start
                    else None,
                    "end": result.processed_query.time_range.end.isoformat()
                    if result.processed_query.time_range.end
                    else None,
                }

            processed_query = ProcessedQueryInfoSchema(
                original_query=result.processed_query.original_query,
                query_type=result.processed_query.query_type.value,
                keywords=result.processed_query.keywords,
                entities=result.processed_query.entities,
                time_range=time_range,
            )

        return SearchResponse(
            results=results,
            total_count=result.total_count,
            query=result.query,
            processed_query=processed_query,
            search_time_ms=result.search_time_ms,
            page=result.page,
            page_size=result.page_size,
            has_more=result.has_more,
        )

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Search failed", "message": str(e)},
        )


@router.post(
    "/advanced",
    response_model=SearchResponse,
    summary="Advanced search",
    description="Search with required filters and optional query.",
)
async def advanced_search(
    request: AdvancedSearchRequest,
    current_user: CurrentUser,
) -> SearchResponse:
    """
    Advanced search with filtering.

    Use this for filter-heavy searches where metadata filtering
    is more important than semantic matching.
    """
    search_service = get_search_service()

    try:
        filters = SearchFilters(
            pst_file_ids=request.filters.pst_file_ids,
            sender_emails=request.filters.sender_emails,
            recipient_emails=request.filters.recipient_emails,
            date_from=request.filters.date_from,
            date_to=request.filters.date_to,
            has_attachments=request.filters.has_attachments,
            folder_paths=request.filters.folder_paths,
            importance=request.filters.importance,
            attachment_types=request.filters.attachment_types,
        )

        result = await search_service.advanced_search(
            filters=filters,
            query=request.query,
            page=request.page,
            page_size=request.page_size,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
        )

        # Convert to response
        results = [
            SearchResultSchema(
                email_id=r.email_id,
                subject=r.subject,
                sender_email=r.sender_email,
                sender_name=r.sender_name,
                sent_date=r.sent_date,
                snippet=r.snippet,
                score=r.score,
                match_type=r.match_type,
                highlights=r.highlights,
                has_attachments=r.has_attachments,
                attachment_count=r.attachment_count,
                folder_path=r.folder_path,
                pst_file_id=r.pst_file_id,
            )
            for r in result.results
        ]

        processed_query = None
        if result.processed_query:
            processed_query = ProcessedQueryInfoSchema(
                original_query=result.processed_query.original_query,
                query_type=result.processed_query.query_type.value,
                keywords=result.processed_query.keywords,
                entities=result.processed_query.entities,
            )

        return SearchResponse(
            results=results,
            total_count=result.total_count,
            query=result.query,
            processed_query=processed_query,
            search_time_ms=result.search_time_ms,
            page=result.page,
            page_size=result.page_size,
            has_more=result.has_more,
        )

    except Exception as e:
        logger.exception(f"Advanced search failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Advanced search failed", "message": str(e)},
        )


@router.post(
    "/suggestions",
    response_model=SuggestionsResponse,
    summary="Get search suggestions",
    description="Get autocomplete suggestions for partial queries.",
)
async def get_suggestions(
    request: SuggestionRequest,
    current_user: CurrentUser,
) -> SuggestionsResponse:
    """
    Get search suggestions for autocomplete.

    Returns suggestions based on email subjects and sender names.
    """
    search_service = get_search_service()

    try:
        suggestions = await search_service.get_suggestions(
            partial_query=request.partial_query,
            limit=request.limit,
        )

        return SuggestionsResponse(
            suggestions=suggestions,
            query=request.partial_query,
        )

    except Exception as e:
        logger.exception(f"Failed to get suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get suggestions"},
        )


@router.get(
    "/facets",
    response_model=FacetsResponse,
    summary="Get search facets",
    description="Get faceted search data for filtering UI.",
)
async def get_facets(
    current_user: CurrentUser,
    pst_file_id: str | None = None,
) -> FacetsResponse:
    """
    Get search facets for building filter UI.

    Returns counts for senders, folders, importance levels.
    """
    search_service = get_search_service()

    try:
        filters = None
        if pst_file_id:
            filters = SearchFilters(pst_file_ids=[pst_file_id])

        facets = await search_service.get_search_facets(filters=filters)

        return FacetsResponse(
            senders=[FacetValue(**f) for f in facets.get("senders", [])],
            folders=[FacetValue(**f) for f in facets.get("folders", [])],
            importance=[FacetValue(**f) for f in facets.get("importance", [])],
        )

    except Exception as e:
        logger.exception(f"Failed to get facets: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to get facets"},
        )


@router.get(
    "/history",
    summary="Get search history",
    description="Get user's recent search queries.",
)
async def get_search_history(
    current_user: CurrentUser,
    limit: int = 20,
) -> list[str]:
    """
    Get the user's recent search history.

    Returns the most recent search queries performed by the user.
    """
    # TODO: Implement proper search history storage
    # For now, return empty list as placeholder
    return []


@router.delete(
    "/history",
    summary="Clear search history",
    description="Clear the user's search history.",
)
async def clear_search_history(
    current_user: CurrentUser,
) -> dict:
    """
    Clear the user's search history.
    """
    # TODO: Implement proper search history clearing
    return {"message": "Search history cleared"}
