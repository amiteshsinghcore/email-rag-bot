"""
RAG API Endpoints

Endpoints for RAG-based email question answering.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger

from app.api.deps import CurrentUser, DbSession, get_current_active_user
from app.config import settings
from app.schemas.rag import (
    AllLLMSettingsResponse,
    ChatRequest,
    ChatResponse,
    LLMProviderInfo,
    LLMSettingsCreate,
    LLMSettingsResponse,
    LLMSettingsUpdate,
    ProcessedQuerySchema,
    ProvidersResponse,
    RAGErrorResponse,
    SearchEnhanceRequest,
    SearchEnhanceResponse,
    SourceSchema,
    SummarizeRequest,
    SummarizeResponse,
    TestApiKeyRequest,
    TestApiKeyResponse,
)
from app.services.llm import LLMProviderError
from app.services.llm_settings_service import get_llm_settings_service
from app.services.query_processor import get_query_processor
from app.services.rag_service import ChatMessage, get_rag_service

router = APIRouter(prefix="/rag", tags=["RAG"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": RAGErrorResponse},
        500: {"model": RAGErrorResponse},
    },
    summary="Chat with emails",
    description="Ask questions about your emails using RAG.",
)
async def chat(
    request: ChatRequest,
    current_user: CurrentUser,
) -> ChatResponse:
    """
    Chat with your emails using RAG.

    Send a question and receive an AI-generated answer based on
    relevant emails from your uploaded PST files.
    """
    # Handle streaming separately
    if request.stream:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /chat/stream endpoint for streaming responses",
        )

    rag_service = get_rag_service()

    # Convert chat history
    chat_history = None
    if request.chat_history:
        chat_history = [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in request.chat_history
        ]

    try:
        response = await rag_service.query(
            question=request.question,
            chat_history=chat_history,
            provider=request.provider,
            model=request.model,
            pst_file_ids=request.pst_file_ids,
            top_k=request.top_k,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_sources=request.include_sources,
        )

        return ChatResponse(
            answer=response.answer,
            sources=[SourceSchema(**s) for s in response.sources],
            query_type=response.query_type,
            processed_query=ProcessedQuerySchema(**response.processed_query)
            if response.processed_query
            else None,
            model_used=response.model_used,
            provider_used=response.provider_used,
            total_tokens=response.total_tokens,
        )

    except LLMProviderError as e:
        logger.error(f"LLM provider error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": e.provider.value if e.provider else None,
            },
        )
    except Exception as e:
        logger.exception(f"RAG query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to process query", "error_type": "InternalError"},
        )


@router.post(
    "/chat/stream",
    summary="Chat with emails (streaming)",
    description="Ask questions about your emails with streaming response.",
)
async def chat_stream(
    request: ChatRequest,
    current_user: CurrentUser,
) -> StreamingResponse:
    """
    Chat with your emails using streaming response.

    Returns server-sent events (SSE) with response chunks.
    """
    rag_service = get_rag_service()

    # Convert chat history
    chat_history = None
    if request.chat_history:
        chat_history = [
            ChatMessage(role=msg.role, content=msg.content)
            for msg in request.chat_history
        ]

    async def event_generator():
        """Generate SSE events."""
        try:
            # Send start event
            yield f"data: {json.dumps({'event': 'start', 'data': {}})}\n\n"

            # Stream response chunks
            async for chunk in rag_service.query_stream(
                question=request.question,
                chat_history=chat_history,
                provider=request.provider,
                model=request.model,
                pst_file_ids=request.pst_file_ids,
                top_k=request.top_k,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield f"data: {json.dumps({'event': 'chunk', 'data': {'content': chunk}})}\n\n"

            # Send end event
            yield f"data: {json.dumps({'event': 'end', 'data': {}})}\n\n"

        except LLMProviderError as e:
            logger.error(f"Streaming LLM error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'data': {'error': str(e), 'error_type': type(e).__name__}})}\n\n"
        except Exception as e:
            logger.exception(f"Streaming error: {e}")
            yield f"data: {json.dumps({'event': 'error', 'data': {'error': 'Stream failed', 'error_type': 'InternalError'}})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    summary="Summarize emails",
    description="Generate a summary of emails.",
)
async def summarize(
    request: SummarizeRequest,
    current_user: CurrentUser,
) -> SummarizeResponse:
    """
    Generate a summary of emails.

    Can summarize all emails, emails from specific PST files,
    or focus on a specific topic.
    """
    rag_service = get_rag_service()

    try:
        response = await rag_service.summarize_emails(
            email_ids=request.email_ids,
            pst_file_ids=request.pst_file_ids,
            topic=request.topic,
            provider=request.provider,
            model=request.model,
            max_emails=request.max_emails,
        )

        return SummarizeResponse(
            summary=response.answer,
            sources=[SourceSchema(**s) for s in response.sources],
            email_count=len(response.sources),
            model_used=response.model_used,
            provider_used=response.provider_used,
        )

    except LLMProviderError as e:
        logger.error(f"Summarization LLM error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": str(e),
                "error_type": type(e).__name__,
                "provider": e.provider.value if e.provider else None,
            },
        )
    except Exception as e:
        logger.exception(f"Summarization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to generate summary", "error_type": "InternalError"},
        )


@router.get(
    "/providers",
    response_model=ProvidersResponse,
    summary="List LLM providers",
    description="Get list of available LLM providers and their status.",
)
async def list_providers(
    current_user: CurrentUser,
    db: DbSession,
) -> ProvidersResponse:
    """
    Get list of available LLM providers.

    Shows which providers are configured and their supported models.
    """
    rag_service = get_rag_service()

    providers_data = await rag_service.get_available_providers()

    # Get LLM settings from database to check which providers have API keys configured
    from app.services.llm_settings_service import LLMSettingsService
    llm_settings_service = LLMSettingsService(db)
    user_id = None if current_user.is_admin else str(current_user.id)

    # Get all settings for current user context
    all_settings = await llm_settings_service.get_all_settings(user_id=user_id)
    db_configured_providers = {s.provider for s in all_settings if s.api_key}

    # Convert to LLMProviderInfo objects
    providers = []
    for p in providers_data:
        # Provider is available if either env var is set OR database has API key
        is_available = p["is_available"] or p["name"] in db_configured_providers
        providers.append(LLMProviderInfo(
            name=p["name"],
            display_name=p["display_name"],
            is_available=is_available,
            models=p.get("models", []),
            default_model=p.get("default_model", ""),
        ))

    # Get default provider from database
    default_provider = await llm_settings_service.get_default_provider(user_id=user_id)
    if not default_provider:
        default_provider = settings.default_llm_provider

    return ProvidersResponse(
        providers=providers,
        default_provider=default_provider,
    )


@router.post(
    "/enhance",
    response_model=SearchEnhanceResponse,
    summary="Enhance search query",
    description="Get query enhancement and suggestions.",
)
async def enhance_query(
    request: SearchEnhanceRequest,
    current_user: CurrentUser,
) -> SearchEnhanceResponse:
    """
    Enhance a search query with processing insights.

    Returns query classification, entity extraction, and suggestions.
    """
    query_processor = get_query_processor()

    try:
        processed = await query_processor.process(request.query)

        return SearchEnhanceResponse(
            original_query=processed.original_query,
            query_type=processed.query_type.value,
            suggestions=processed.sub_queries,
            expanded_terms=processed.expanded_terms,
            entities=processed.entities,
            time_range={
                "start": processed.time_range.start.isoformat()
                if processed.time_range and processed.time_range.start
                else None,
                "end": processed.time_range.end.isoformat()
                if processed.time_range and processed.time_range.end
                else None,
            }
            if processed.time_range
            else None,
        )

    except Exception as e:
        logger.exception(f"Query enhancement failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Failed to enhance query", "error_type": "InternalError"},
        )


@router.get(
    "/health",
    summary="RAG health check",
    description="Check RAG service health.",
)
async def health_check() -> dict[str, Any]:
    """
    Check RAG service health.

    Verifies that all required services are available.
    """
    from app.services.embedding_service import embedding_service
    from app.services.vector_store import vector_store

    health = {
        "status": "healthy",
        "components": {},
    }

    # Check embedding service
    try:
        # Try to generate a test embedding
        test_embedding = embedding_service.generate_embedding("test")
        health["components"]["embedding_service"] = {
            "status": "healthy",
            "dimension": len(test_embedding),
        }
    except Exception as e:
        health["components"]["embedding_service"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check vector store
    try:
        stats = vector_store.get_collection_stats()
        health["components"]["vector_store"] = {
            "status": "healthy",
            **stats,
        }
    except Exception as e:
        health["components"]["vector_store"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    # Check default LLM provider
    try:
        from app.services.llm import LLMFactory

        llm = LLMFactory.get_provider()
        health["components"]["llm"] = {
            "status": "healthy" if llm.validate_api_key() else "not_configured",
            "provider": settings.default_llm_provider,
            "model": llm.model,
        }
    except Exception as e:
        health["components"]["llm"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        health["status"] = "degraded"

    return health


@router.post(
    "/test-api-key",
    response_model=TestApiKeyResponse,
    summary="Test LLM API key",
    description="Test if an LLM API key is valid by making a simple request.",
)
async def test_api_key(
    request: TestApiKeyRequest,
    current_user: CurrentUser,
) -> TestApiKeyResponse:
    """
    Test an LLM API key.

    Makes a minimal API call to verify the key works.
    Does not store the key - it's for testing purposes only.
    """
    from app.services.llm import LLMFactory
    from app.services.llm.base import Message

    try:
        # Get provider with the test API key
        kwargs = {}
        if request.base_url:
            kwargs["base_url"] = request.base_url

        provider = LLMFactory.get_provider(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            **kwargs,
        )

        # Make a minimal test request
        test_messages = [
            Message(role="user", content="Say 'OK' if you can read this.")
        ]

        response = await provider.generate(
            messages=test_messages,
            max_tokens=10,
            temperature=0.0,
        )

        return TestApiKeyResponse(
            success=True,
            provider=request.provider,
            model=response.model,
            message=f"API key is valid. Response: {response.content[:50]}...",
            error=None,
        )

    except LLMProviderError as e:
        logger.warning(f"API key test failed for {request.provider}: {e}")
        return TestApiKeyResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            message="API key test failed",
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error testing API key for {request.provider}: {e}")
        return TestApiKeyResponse(
            success=False,
            provider=request.provider,
            model=request.model,
            message="Unexpected error during API key test",
            error=str(e),
        )


# ===========================================
# LLM Settings Endpoints
# ===========================================


@router.get(
    "/settings",
    response_model=AllLLMSettingsResponse,
    summary="Get LLM settings",
    description="Get all configured LLM provider settings.",
)
async def get_llm_settings(
    db: DbSession,
    current_user: CurrentUser,
) -> AllLLMSettingsResponse:
    """
    Get all LLM provider settings.

    Returns configured settings for all providers.
    API keys are masked for security.
    """
    service = get_llm_settings_service(db)

    # Get settings (user-specific if not admin, otherwise system-wide)
    all_settings = await service.get_all_settings(
        user_id=None if current_user.is_admin else str(current_user.id)
    )

    # Get default provider
    default_provider = await service.get_default_provider(
        user_id=None if current_user.is_admin else str(current_user.id)
    )

    return AllLLMSettingsResponse(
        settings=[
            LLMSettingsResponse(
                id=str(s.id),
                provider=s.provider,
                user_id=str(s.user_id) if s.user_id else None,
                api_key_set=bool(s.api_key),
                api_key_preview=s._mask_api_key(),
                model=s.model,
                base_url=s.base_url,
                is_enabled=s.is_enabled,
                is_default=s.is_default,
                created_at=s.created_at.isoformat() if s.created_at else None,
                updated_at=s.updated_at.isoformat() if s.updated_at else None,
            )
            for s in all_settings
        ],
        default_provider=default_provider,
    )


@router.post(
    "/settings",
    response_model=LLMSettingsResponse,
    summary="Create or update LLM settings",
    description="Create or update settings for an LLM provider.",
)
async def create_or_update_llm_settings(
    request: LLMSettingsCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> LLMSettingsResponse:
    """
    Create or update LLM settings for a provider.

    Admins can set system-wide settings, others set user-specific settings.
    """
    service = get_llm_settings_service(db)

    # Admins set system-wide settings, non-admins set user-specific settings
    user_id = None if current_user.is_admin else str(current_user.id)

    try:
        settings_obj = await service.create_or_update_settings(
            provider=request.provider,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
            is_enabled=request.is_enabled,
            is_default=request.is_default,
            user_id=user_id,
        )

        return LLMSettingsResponse(
            id=str(settings_obj.id),
            provider=settings_obj.provider,
            user_id=str(settings_obj.user_id) if settings_obj.user_id else None,
            api_key_set=bool(settings_obj.api_key),
            api_key_preview=settings_obj._mask_api_key(),
            model=settings_obj.model,
            base_url=settings_obj.base_url,
            is_enabled=settings_obj.is_enabled,
            is_default=settings_obj.is_default,
            created_at=settings_obj.created_at.isoformat() if settings_obj.created_at else None,
            updated_at=settings_obj.updated_at.isoformat() if settings_obj.updated_at else None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/settings/{settings_id}",
    response_model=LLMSettingsResponse,
    summary="Update LLM settings",
    description="Update existing LLM provider settings.",
)
async def update_llm_settings(
    settings_id: str,
    request: LLMSettingsUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> LLMSettingsResponse:
    """
    Update existing LLM settings by ID.

    Users can update their own settings, admins can update system-wide settings.
    """
    service = get_llm_settings_service(db)

    settings_obj = await service.update_settings(
        settings_id=settings_id,
        api_key=request.api_key,
        model=request.model,
        base_url=request.base_url,
        is_enabled=request.is_enabled,
        is_default=request.is_default,
    )

    if not settings_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settings not found",
        )

    return LLMSettingsResponse(
        id=str(settings_obj.id),
        provider=settings_obj.provider,
        user_id=str(settings_obj.user_id) if settings_obj.user_id else None,
        api_key_set=bool(settings_obj.api_key),
        api_key_preview=settings_obj._mask_api_key(),
        model=settings_obj.model,
        base_url=settings_obj.base_url,
        is_enabled=settings_obj.is_enabled,
        is_default=settings_obj.is_default,
        created_at=settings_obj.created_at.isoformat() if settings_obj.created_at else None,
        updated_at=settings_obj.updated_at.isoformat() if settings_obj.updated_at else None,
    )


@router.delete(
    "/settings/{settings_id}",
    summary="Delete LLM settings",
    description="Delete LLM provider settings.",
)
async def delete_llm_settings(
    settings_id: str,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """
    Delete LLM settings by ID.

    Users can delete their own settings, admins can delete system-wide settings.
    """
    service = get_llm_settings_service(db)

    success = await service.delete_settings(settings_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settings not found",
        )

    return {"message": "Settings deleted successfully"}


@router.post(
    "/settings/{provider}/set-default",
    summary="Set default provider",
    description="Set a provider as the default LLM provider.",
)
async def set_default_provider(
    provider: str,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """
    Set a provider as the default.

    Admins set system-wide default, others set user-specific default.
    """
    service = get_llm_settings_service(db)

    # Admins set system-wide default, non-admins set user-specific default
    user_id = None if current_user.is_admin else str(current_user.id)
    success = await service.set_default_provider(provider, user_id=user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Provider settings not found. Configure the provider first.",
        )

    return {"message": f"Set {provider} as default provider"}
