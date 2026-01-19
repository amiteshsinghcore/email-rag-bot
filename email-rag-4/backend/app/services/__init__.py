"""
Services Package

Contains business logic services for the application.
"""

from app.services.attachment_processor import (
    AttachmentProcessor,
    AttachmentProcessorError,
    UnsupportedFormatError,
    attachment_processor,
    get_attachment_processor,
)
from app.services.email_service import (
    EmailDetail,
    EmailListResponse,
    EmailService,
    EmailSummary,
    EmailThread,
    email_service,
    get_email_service,
)
from app.services.embedding_service import (
    EmbeddingService,
    TextChunk,
    embedding_service,
    get_embedding_service,
)
from app.services.pst_processor import (
    ExtractedAttachment,
    ExtractedEmail,
    PSTFileNotFoundError,
    PSTParseError,
    PSTProcessor,
    PSTProcessorError,
    create_pst_processor,
)
from app.services.query_processor import (
    ProcessedQuery,
    QueryProcessor,
    QueryType,
    get_query_processor,
    query_processor,
)
from app.services.rag_service import (
    ChatMessage,
    RAGResponse,
    RAGService,
    get_rag_service,
    rag_service,
)
from app.services.retrieval_service import (
    RetrievalResult,
    RetrievalService,
    RetrievedDocument,
    get_retrieval_service,
    retrieval_service,
)
from app.services.search_service import (
    SearchFilters,
    SearchResponse,
    SearchResult,
    SearchService,
    get_search_service,
    search_service,
)
from app.services.user_service import UserService, get_user_service
from app.services.vector_store import VectorStoreService, get_vector_store, vector_store

__all__ = [
    # Vector Store
    "VectorStoreService",
    "vector_store",
    "get_vector_store",
    # User Service
    "UserService",
    "get_user_service",
    # PST Processor
    "PSTProcessor",
    "PSTProcessorError",
    "PSTFileNotFoundError",
    "PSTParseError",
    "ExtractedEmail",
    "ExtractedAttachment",
    "create_pst_processor",
    # Attachment Processor
    "AttachmentProcessor",
    "AttachmentProcessorError",
    "UnsupportedFormatError",
    "attachment_processor",
    "get_attachment_processor",
    # Embedding Service
    "EmbeddingService",
    "TextChunk",
    "embedding_service",
    "get_embedding_service",
    # Query Processor
    "QueryProcessor",
    "QueryType",
    "ProcessedQuery",
    "query_processor",
    "get_query_processor",
    # Retrieval Service
    "RetrievalService",
    "RetrievalResult",
    "RetrievedDocument",
    "retrieval_service",
    "get_retrieval_service",
    # RAG Service
    "RAGService",
    "RAGResponse",
    "ChatMessage",
    "rag_service",
    "get_rag_service",
    # Search Service
    "SearchService",
    "SearchResult",
    "SearchResponse",
    "SearchFilters",
    "search_service",
    "get_search_service",
    # Email Service
    "EmailService",
    "EmailSummary",
    "EmailDetail",
    "EmailThread",
    "EmailListResponse",
    "email_service",
    "get_email_service",
]
