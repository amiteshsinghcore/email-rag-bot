"""
Retrieval Service

Handles document retrieval from vector store with filtering and re-ranking.
"""

from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from app.services.embedding_service import embedding_service
from app.services.query_processor import ProcessedQuery, QueryType
from app.services.vector_store import vector_store


@dataclass
class RetrievedDocument:
    """A document retrieved from the vector store."""

    id: str
    content: str
    score: float  # Similarity score (0-1, higher is better)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_type: str = "email"  # "email" or "attachment"
    rerank_score: float | None = None


@dataclass
class RetrievalResult:
    """Result of a retrieval operation."""

    documents: list[RetrievedDocument]
    query: str
    total_retrieved: int
    metadata_filters_applied: dict[str, Any] = field(default_factory=dict)


class RetrievalService:
    """
    Service for retrieving relevant documents from the vector store.

    Features:
    - Vector similarity search
    - Metadata filtering
    - Hybrid search (vector + full-text)
    - Result re-ranking
    - HyDE-based retrieval
    """

    DEFAULT_TOP_K = 30
    MAX_TOP_K = 100

    def __init__(self) -> None:
        """Initialize retrieval service."""
        pass

    async def retrieve(
        self,
        query: str,
        processed_query: ProcessedQuery | None = None,
        top_k: int = DEFAULT_TOP_K,
        include_attachments: bool = True,
        metadata_filters: dict[str, Any] | None = None,
        pst_file_ids: list[str] | None = None,
        use_hyde: bool = True,
        rerank: bool = True,
    ) -> RetrievalResult:
        """
        Retrieve relevant documents for a query.

        Args:
            query: User query text
            processed_query: Pre-processed query (optional)
            top_k: Number of documents to retrieve
            include_attachments: Whether to search attachments
            metadata_filters: Additional metadata filters
            pst_file_ids: Filter to specific PST files
            use_hyde: Use HyDE for better retrieval
            rerank: Apply re-ranking to results

        Returns:
            RetrievalResult with ranked documents
        """
        top_k = min(top_k, self.MAX_TOP_K)

        # Build combined filters
        filters = self._build_filters(
            processed_query=processed_query,
            metadata_filters=metadata_filters,
            pst_file_ids=pst_file_ids,
        )

        # Determine query text for embedding
        query_for_embedding = query
        if use_hyde and processed_query and processed_query.hyde_document:
            query_for_embedding = processed_query.hyde_document
            logger.debug("Using HyDE document for retrieval")

        # Generate query embedding
        query_embedding = await embedding_service.embed_query(query_for_embedding)

        # Search emails
        email_results = await self._search_emails(
            query_embedding=query_embedding,
            top_k=top_k,
            filters=filters,
        )

        # Optionally search attachments
        attachment_results = []
        if include_attachments:
            attachment_results = await self._search_attachments(
                query_embedding=query_embedding,
                top_k=top_k // 2,  # Half the quota for attachments
                filters=filters,
            )

        # Combine and deduplicate results
        all_results = self._merge_results(
            email_results=email_results,
            attachment_results=attachment_results,
        )

        # Apply re-ranking if enabled
        if rerank and len(all_results) > 0:
            all_results = await self._rerank_results(
                query=query,
                results=all_results,
                processed_query=processed_query,
            )

        # Take top k after re-ranking
        final_results = all_results[:top_k]

        return RetrievalResult(
            documents=final_results,
            query=query,
            total_retrieved=len(all_results),
            metadata_filters_applied=filters,
        )

    async def retrieve_for_query_type(
        self,
        query: str,
        query_type: QueryType,
        processed_query: ProcessedQuery,
        top_k: int = DEFAULT_TOP_K,
        **kwargs: Any,
    ) -> RetrievalResult:
        """
        Retrieve documents optimized for specific query types.

        Different query types benefit from different retrieval strategies.
        """
        # Adjust strategy based on query type
        if query_type == QueryType.RELATIONAL:
            # For relational queries, focus on email participants
            return await self._retrieve_relational(
                processed_query=processed_query,
                top_k=top_k,
                **kwargs,
            )

        elif query_type == QueryType.ATTACHMENT:
            # For attachment queries, prioritize attachment search
            return await self.retrieve(
                query=query,
                processed_query=processed_query,
                top_k=top_k,
                include_attachments=True,
                **kwargs,
            )

        elif query_type == QueryType.ANALYTICAL:
            # For analytical queries, retrieve more documents for aggregation
            return await self.retrieve(
                query=query,
                processed_query=processed_query,
                top_k=min(top_k * 3, self.MAX_TOP_K),
                include_attachments=False,
                **kwargs,
            )

        else:
            # Default retrieval
            return await self.retrieve(
                query=query,
                processed_query=processed_query,
                top_k=top_k,
                **kwargs,
            )

    async def multi_query_retrieve(
        self,
        queries: list[str],
        top_k_per_query: int = 5,
        deduplicate: bool = True,
        **kwargs: Any,
    ) -> RetrievalResult:
        """
        Retrieve documents using multiple query variations.

        Useful for complex queries that benefit from multiple perspectives.

        Args:
            queries: List of query variations
            top_k_per_query: Number of results per query
            deduplicate: Remove duplicate documents
            **kwargs: Additional retrieval options

        Returns:
            Combined retrieval result
        """
        all_docs: list[RetrievedDocument] = []
        seen_ids: set[str] = set()

        for query in queries:
            result = await self.retrieve(
                query=query,
                top_k=top_k_per_query,
                rerank=False,  # Rerank after combining
                **kwargs,
            )

            for doc in result.documents:
                if deduplicate:
                    if doc.id not in seen_ids:
                        all_docs.append(doc)
                        seen_ids.add(doc.id)
                else:
                    all_docs.append(doc)

        # Sort by score
        all_docs.sort(key=lambda x: x.score, reverse=True)

        return RetrievalResult(
            documents=all_docs,
            query=" | ".join(queries),
            total_retrieved=len(all_docs),
        )

    async def _search_emails(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[RetrievedDocument]:
        """Search email embeddings."""
        # Build ChromaDB where clause
        where_clause = self._build_chroma_where(filters) if filters else None

        results = vector_store.search_emails(
            query_embedding=query_embedding,
            n_results=top_k,
            where=where_clause,
        )

        # Convert to RetrievedDocument objects
        documents = []
        for i, doc_id in enumerate(results["ids"]):
            # Convert distance to similarity score (cosine distance to similarity)
            distance = results["distances"][i] if results["distances"] else 0
            similarity = 1 - distance  # For cosine distance

            documents.append(
                RetrievedDocument(
                    id=doc_id,
                    content=results["documents"][i] if results["documents"] else "",
                    score=similarity,
                    metadata=results["metadatas"][i] if results["metadatas"] else {},
                    source_type="email",
                )
            )

        return documents

    async def _search_attachments(
        self,
        query_embedding: list[float],
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[RetrievedDocument]:
        """Search attachment embeddings."""
        where_clause = self._build_chroma_where(filters) if filters else None

        results = vector_store.search_attachments(
            query_embedding=query_embedding,
            n_results=top_k,
            where=where_clause,
        )

        documents = []
        for i, doc_id in enumerate(results["ids"]):
            distance = results["distances"][i] if results["distances"] else 0
            similarity = 1 - distance

            documents.append(
                RetrievedDocument(
                    id=doc_id,
                    content=results["documents"][i] if results["documents"] else "",
                    score=similarity,
                    metadata=results["metadatas"][i] if results["metadatas"] else {},
                    source_type="attachment",
                )
            )

        return documents

    async def _retrieve_relational(
        self,
        processed_query: ProcessedQuery,
        top_k: int,
        **kwargs: Any,
    ) -> RetrievalResult:
        """Retrieve documents for relational queries (between persons)."""
        # Extract email entities
        email_entities = [e for e in processed_query.entities if "@" in e]

        if not email_entities:
            # Fall back to standard retrieval
            return await self.retrieve(
                query=processed_query.original_query,
                processed_query=processed_query,
                top_k=top_k,
                **kwargs,
            )

        # Build filter for participants
        filters = {"participants": email_entities}

        return await self.retrieve(
            query=processed_query.original_query,
            processed_query=processed_query,
            top_k=top_k,
            metadata_filters=filters,
            **kwargs,
        )

    def _build_filters(
        self,
        processed_query: ProcessedQuery | None,
        metadata_filters: dict[str, Any] | None,
        pst_file_ids: list[str] | None,
    ) -> dict[str, Any]:
        """Build combined metadata filters."""
        filters: dict[str, Any] = {}

        # Add processed query filters
        if processed_query and processed_query.metadata_filters:
            filters.update(processed_query.metadata_filters)

        # Add explicit metadata filters
        if metadata_filters:
            filters.update(metadata_filters)

        # Add PST file filter
        if pst_file_ids:
            filters["pst_file_id"] = pst_file_ids

        return filters

    def _build_chroma_where(self, filters: dict[str, Any]) -> dict[str, Any] | None:
        """Convert filters to ChromaDB where clause format."""
        if not filters:
            return None

        conditions = []

        for key, value in filters.items():
            if key == "pst_file_id":
                if isinstance(value, list):
                    conditions.append({"pst_file_id": {"$in": value}})
                else:
                    conditions.append({"pst_file_id": value})

            elif key == "participants":
                # Match sender or recipient
                if isinstance(value, list):
                    if len(value) == 1:
                        # Single participant - use direct match (ChromaDB requires $or to have 2+ items)
                        conditions.append({"sender": value[0]})
                    elif len(value) > 1:
                        # Multiple participants - use $or clause
                        participant_conditions = [{"sender": p} for p in value]
                        conditions.append({"$or": participant_conditions})
                else:
                    conditions.append({"sender": value})

            elif key == "date_gte":
                conditions.append({"date": {"$gte": value}})

            elif key == "date_lte":
                conditions.append({"date": {"$lte": value}})

            else:
                conditions.append({key: value})

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    def _merge_results(
        self,
        email_results: list[RetrievedDocument],
        attachment_results: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        """Merge and deduplicate email and attachment results."""
        all_results = email_results + attachment_results

        # Sort by score
        all_results.sort(key=lambda x: x.score, reverse=True)

        # Deduplicate by email_id (prefer higher scores)
        seen_emails: set[str] = set()
        deduped_results: list[RetrievedDocument] = []

        for doc in all_results:
            email_id = doc.metadata.get("email_id", doc.id)

            # For attachments, we might want to keep both email and attachment
            if doc.source_type == "attachment":
                if doc.id not in seen_emails:
                    deduped_results.append(doc)
                    seen_emails.add(doc.id)
            else:
                if email_id not in seen_emails:
                    deduped_results.append(doc)
                    seen_emails.add(email_id)

        return deduped_results

    async def _rerank_results(
        self,
        query: str,
        results: list[RetrievedDocument],
        processed_query: ProcessedQuery | None = None,
    ) -> list[RetrievedDocument]:
        """
        Re-rank results for better relevance.

        Uses a simple scoring adjustment based on:
        - Keyword matches
        - Entity matches
        - Recency (if temporal query)
        """
        if not results:
            return results

        # Get query keywords for matching
        query_lower = query.lower()
        keywords = set(query_lower.split())

        # Get entities if available
        entities = set()
        if processed_query:
            entities = {e.lower() for e in processed_query.entities}

        for doc in results:
            rerank_bonus = 0.0
            content_lower = doc.content.lower()
            metadata = doc.metadata

            # Keyword match bonus
            keyword_matches = sum(1 for kw in keywords if kw in content_lower)
            rerank_bonus += keyword_matches * 0.02

            # Entity match bonus
            entity_matches = sum(1 for e in entities if e in content_lower)
            rerank_bonus += entity_matches * 0.05

            # Subject match bonus (strong signal)
            subject = metadata.get("subject", "").lower()
            if any(kw in subject for kw in keywords):
                rerank_bonus += 0.1

            # Sender/recipient match
            sender = metadata.get("sender", "").lower()
            if sender in entities or any(kw in sender for kw in keywords):
                rerank_bonus += 0.05

            # Calculate final score
            doc.rerank_score = doc.score + rerank_bonus

        # Sort by rerank score
        results.sort(key=lambda x: x.rerank_score or x.score, reverse=True)

        return results


# Global instance
retrieval_service = RetrievalService()


def get_retrieval_service() -> RetrievalService:
    """Get the retrieval service instance."""
    return retrieval_service
