"""
Search Service

Provides natural language and advanced search capabilities for emails.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.attachment import Attachment
from app.db.models.email import Email
from app.db.session import get_db_context
from app.services.embedding_service import get_embedding_service
from app.services.query_processor import ProcessedQuery, get_query_processor
from app.services.vector_store import get_vector_store


@dataclass
class SearchResult:
    """A single search result."""

    email_id: str
    subject: str | None
    sender_email: str | None
    sender_name: str | None
    sent_date: datetime | None
    snippet: str | None  # Preview of matching content
    score: float = 0.0
    match_type: str = "semantic"  # "semantic", "fulltext", "hybrid"
    highlights: list[str] = field(default_factory=list)
    has_attachments: bool = False
    attachment_count: int = 0
    folder_path: str | None = None
    pst_file_id: str | None = None


@dataclass
class SearchResponse:
    """Search response with results and metadata."""

    results: list[SearchResult]
    total_count: int
    query: str
    processed_query: ProcessedQuery | None = None
    search_time_ms: float = 0.0
    page: int = 1
    page_size: int = 20
    has_more: bool = False


@dataclass
class SearchFilters:
    """Filters for advanced search."""

    pst_file_ids: list[str] | None = None
    sender_emails: list[str] | None = None
    recipient_emails: list[str] | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    has_attachments: bool | None = None
    folder_paths: list[str] | None = None
    importance: str | None = None
    attachment_types: list[str] | None = None


class SearchService:
    """
    Service for searching emails.

    Supports:
    - Natural language semantic search using vector embeddings
    - Full-text search using PostgreSQL tsvector
    - Hybrid search combining both approaches
    - Advanced filtering by metadata
    """

    def __init__(self) -> None:
        """Initialize search service."""
        self._query_processor = get_query_processor()
        self._embedding_service = get_embedding_service()
        self._vector_store = get_vector_store()

    async def search(
        self,
        query: str,
        filters: SearchFilters | None = None,
        page: int = 1,
        page_size: int = 20,
        search_type: str = "hybrid",  # "semantic", "fulltext", "hybrid"
        include_attachments: bool = True,
    ) -> SearchResponse:
        """
        Search emails using natural language query.

        Args:
            query: Natural language search query
            filters: Optional filters to narrow results
            page: Page number (1-indexed)
            page_size: Number of results per page
            search_type: Type of search to perform
            include_attachments: Whether to include attachment content in search

        Returns:
            SearchResponse with results and metadata
        """
        import time

        start_time = time.time()

        # Process the query
        processed_query = await self._query_processor.process(query)
        logger.debug(f"Processed query: {processed_query}")

        # Build ChromaDB where clause from filters
        chroma_where = self._build_chroma_filters(filters)

        results: list[SearchResult] = []

        if search_type in ("semantic", "hybrid"):
            # Semantic search using embeddings
            semantic_results = await self._semantic_search(
                processed_query,
                filters=filters,
                chroma_where=chroma_where,
                limit=page_size * 2,  # Get more for merging
                include_attachments=include_attachments,
            )
            results.extend(semantic_results)

        if search_type in ("fulltext", "hybrid"):
            # Full-text search using PostgreSQL
            fulltext_results = await self._fulltext_search(
                processed_query,
                filters=filters,
                limit=page_size * 2,
            )
            results.extend(fulltext_results)

        # Deduplicate and merge results
        if search_type == "hybrid":
            results = self._merge_results(results)
        else:
            # Simple deduplication
            seen_ids = set()
            unique_results = []
            for result in results:
                if result.email_id not in seen_ids:
                    seen_ids.add(result.email_id)
                    unique_results.append(result)
            results = unique_results

        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)

        # Apply pagination
        total_count = len(results)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = results[start_idx:end_idx]

        # Enrich results with email details
        paginated_results = await self._enrich_results(paginated_results)

        search_time = (time.time() - start_time) * 1000

        return SearchResponse(
            results=paginated_results,
            total_count=total_count,
            query=query,
            processed_query=processed_query,
            search_time_ms=search_time,
            page=page,
            page_size=page_size,
            has_more=end_idx < total_count,
        )

    async def advanced_search(
        self,
        filters: SearchFilters,
        query: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "sent_date",
        sort_order: str = "desc",
    ) -> SearchResponse:
        """
        Advanced search with filtering and optional query.

        Args:
            filters: Required filters for the search
            query: Optional search query to combine with filters
            page: Page number
            page_size: Results per page
            sort_by: Field to sort by
            sort_order: Sort direction ("asc" or "desc")

        Returns:
            SearchResponse with results
        """
        import time

        start_time = time.time()

        processed_query = None
        if query:
            processed_query = await self._query_processor.process(query)

        async with get_db_context() as db:
            # Build base query
            stmt = select(Email)
            stmt = self._apply_sql_filters(stmt, filters)

            # Apply text search if query provided
            if query and processed_query:
                # Use full-text search
                search_query = " & ".join(processed_query.keywords) if processed_query.keywords else query
                stmt = stmt.where(
                    Email.search_vector.op("@@")(
                        func.plainto_tsquery("english", search_query)
                    )
                )

            # Apply sorting
            sort_column = getattr(Email, sort_by, Email.sent_date)
            if sort_order == "desc":
                stmt = stmt.order_by(sort_column.desc().nulls_last())
            else:
                stmt = stmt.order_by(sort_column.asc().nulls_first())

            # Get total count
            count_stmt = select(func.count()).select_from(stmt.subquery())
            total_count = await db.scalar(count_stmt) or 0

            # Apply pagination
            offset = (page - 1) * page_size
            stmt = stmt.offset(offset).limit(page_size)

            # Execute query
            result = await db.execute(stmt)
            emails = result.scalars().all()

            # Convert to search results
            results = []
            for email in emails:
                snippet = self._generate_snippet(email.body_text, query) if query else None
                results.append(
                    SearchResult(
                        email_id=str(email.id),
                        subject=email.subject,
                        sender_email=email.sender_email,
                        sender_name=email.sender_name,
                        sent_date=email.sent_date,
                        snippet=snippet,
                        score=1.0,  # No scoring for filter-only search
                        match_type="filter",
                        has_attachments=email.has_attachments,
                        attachment_count=len(email.attachments) if email.attachments else 0,
                        folder_path=email.folder_path,
                        pst_file_id=str(email.pst_file_id),
                    )
                )

        search_time = (time.time() - start_time) * 1000

        return SearchResponse(
            results=results,
            total_count=total_count,
            query=query or "",
            processed_query=processed_query,
            search_time_ms=search_time,
            page=page,
            page_size=page_size,
            has_more=(page * page_size) < total_count,
        )

    async def get_suggestions(
        self,
        partial_query: str,
        limit: int = 5,
    ) -> list[str]:
        """
        Get search suggestions based on partial query.

        Args:
            partial_query: Partial search query
            limit: Maximum suggestions to return

        Returns:
            List of suggested queries
        """
        suggestions = []

        async with get_db_context() as db:
            # Get suggestions from subjects
            stmt = (
                select(Email.subject)
                .where(Email.subject.ilike(f"%{partial_query}%"))
                .distinct()
                .limit(limit)
            )
            result = await db.execute(stmt)
            subjects = result.scalars().all()
            suggestions.extend([s for s in subjects if s])

            # Get suggestions from sender names
            if len(suggestions) < limit:
                stmt = (
                    select(Email.sender_name)
                    .where(Email.sender_name.ilike(f"%{partial_query}%"))
                    .distinct()
                    .limit(limit - len(suggestions))
                )
                result = await db.execute(stmt)
                names = result.scalars().all()
                suggestions.extend([n for n in names if n])

        return suggestions[:limit]

    async def get_search_facets(
        self,
        query: str | None = None,
        filters: SearchFilters | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Get faceted search data for filtering UI.

        Returns counts for various filter options.
        """
        facets: dict[str, list[dict[str, Any]]] = {
            "senders": [],
            "folders": [],
            "date_ranges": [],
            "importance": [],
        }

        async with get_db_context() as db:
            # Top senders
            stmt = (
                select(Email.sender_email, func.count(Email.id).label("count"))
                .group_by(Email.sender_email)
                .order_by(text("count DESC"))
                .limit(10)
            )
            if filters:
                stmt = self._apply_sql_filters(stmt, filters)
            result = await db.execute(stmt)
            for row in result:
                if row.sender_email:
                    facets["senders"].append({
                        "value": row.sender_email,
                        "count": row.count,
                    })

            # Folder paths
            stmt = (
                select(Email.folder_path, func.count(Email.id).label("count"))
                .group_by(Email.folder_path)
                .order_by(text("count DESC"))
                .limit(10)
            )
            if filters:
                stmt = self._apply_sql_filters(stmt, filters)
            result = await db.execute(stmt)
            for row in result:
                if row.folder_path:
                    facets["folders"].append({
                        "value": row.folder_path,
                        "count": row.count,
                    })

            # Importance levels
            stmt = (
                select(Email.importance, func.count(Email.id).label("count"))
                .group_by(Email.importance)
                .order_by(text("count DESC"))
            )
            if filters:
                stmt = self._apply_sql_filters(stmt, filters)
            result = await db.execute(stmt)
            for row in result:
                facets["importance"].append({
                    "value": row.importance,
                    "count": row.count,
                })

        return facets

    async def _semantic_search(
        self,
        processed_query: ProcessedQuery,
        filters: SearchFilters | None,
        chroma_where: dict[str, Any] | None,
        limit: int,
        include_attachments: bool,
    ) -> list[SearchResult]:
        """Perform semantic search using embeddings."""
        results: list[SearchResult] = []

        # Generate query embedding
        query_text = processed_query.processed_query or processed_query.original_query

        # Use HyDE document if available
        if processed_query.hyde_document:
            query_text = processed_query.hyde_document

        query_embedding = self._embedding_service.generate_embedding(query_text)

        # Search emails
        email_results = self._vector_store.search_emails(
            query_embedding=query_embedding,
            n_results=limit,
            where=chroma_where,
        )

        # Process email results
        for i, email_id in enumerate(email_results["ids"]):
            # Extract actual email_id from chunk_id if needed
            actual_email_id = email_id.split("_chunk_")[0] if "_chunk_" in email_id else email_id

            metadata = email_results["metadatas"][i] if email_results["metadatas"] else {}
            distance = email_results["distances"][i] if email_results["distances"] else 0
            document = email_results["documents"][i] if email_results["documents"] else ""

            # Convert distance to score (cosine distance to similarity)
            score = 1 - distance if distance else 0

            results.append(
                SearchResult(
                    email_id=metadata.get("email_id", actual_email_id),
                    subject=metadata.get("subject"),
                    sender_email=metadata.get("sender_email"),
                    sender_name=metadata.get("sender_name"),
                    sent_date=self._parse_date(metadata.get("sent_date")),
                    snippet=document[:200] if document else None,
                    score=score,
                    match_type="semantic",
                    pst_file_id=metadata.get("pst_file_id"),
                )
            )

        # Search attachments if requested
        if include_attachments:
            attachment_results = self._vector_store.search_attachments(
                query_embedding=query_embedding,
                n_results=limit // 2,
                where=chroma_where,
            )

            for i, att_id in enumerate(attachment_results["ids"]):
                metadata = attachment_results["metadatas"][i] if attachment_results["metadatas"] else {}
                distance = attachment_results["distances"][i] if attachment_results["distances"] else 0
                document = attachment_results["documents"][i] if attachment_results["documents"] else ""

                score = 1 - distance if distance else 0

                # Attachment results point to parent email
                email_id = metadata.get("email_id", "")
                if email_id:
                    results.append(
                        SearchResult(
                            email_id=email_id,
                            subject=f"Attachment: {metadata.get('filename', 'Unknown')}",
                            sender_email=metadata.get("sender_email"),
                            sender_name=None,
                            sent_date=self._parse_date(metadata.get("sent_date")),
                            snippet=document[:200] if document else None,
                            score=score * 0.9,  # Slight penalty for attachment matches
                            match_type="semantic",
                            pst_file_id=metadata.get("pst_file_id"),
                        )
                    )

        return results

    async def _fulltext_search(
        self,
        processed_query: ProcessedQuery,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[SearchResult]:
        """Perform full-text search using PostgreSQL."""
        results: list[SearchResult] = []

        # Build search query from keywords
        if processed_query.keywords:
            search_terms = " | ".join(processed_query.keywords)
        else:
            search_terms = processed_query.original_query

        async with get_db_context() as db:
            # Build query with ranking
            stmt = (
                select(
                    Email,
                    func.ts_rank_cd(
                        Email.search_vector,
                        func.plainto_tsquery("english", search_terms),
                    ).label("rank"),
                )
                .where(
                    Email.search_vector.op("@@")(
                        func.plainto_tsquery("english", search_terms)
                    )
                )
                .order_by(text("rank DESC"))
                .limit(limit)
            )

            # Apply filters
            if filters:
                stmt = self._apply_sql_filters(stmt, filters)

            result = await db.execute(stmt)
            rows = result.all()

            for row in rows:
                email = row[0]
                rank = row[1]

                # Generate snippet with highlights
                snippet = self._generate_snippet(email.body_text, processed_query.original_query)

                results.append(
                    SearchResult(
                        email_id=str(email.id),
                        subject=email.subject,
                        sender_email=email.sender_email,
                        sender_name=email.sender_name,
                        sent_date=email.sent_date,
                        snippet=snippet,
                        score=float(rank) if rank else 0,
                        match_type="fulltext",
                        has_attachments=email.has_attachments,
                        folder_path=email.folder_path,
                        pst_file_id=str(email.pst_file_id),
                    )
                )

        return results

    def _merge_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Merge and deduplicate results from multiple search types."""
        # Group by email_id
        grouped: dict[str, list[SearchResult]] = {}
        for result in results:
            if result.email_id not in grouped:
                grouped[result.email_id] = []
            grouped[result.email_id].append(result)

        # Merge each group
        merged: list[SearchResult] = []
        for email_id, group in grouped.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Combine scores using RRF (Reciprocal Rank Fusion)
                # Higher weight for semantic matches
                best_result = group[0]
                combined_score = 0.0

                for result in group:
                    if result.match_type == "semantic":
                        combined_score += result.score * 0.6
                    else:
                        combined_score += result.score * 0.4

                best_result.score = combined_score
                best_result.match_type = "hybrid"
                merged.append(best_result)

        return merged

    async def _enrich_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Enrich search results with additional email details."""
        if not results:
            return results

        email_ids = [r.email_id for r in results]

        async with get_db_context() as db:
            stmt = (
                select(Email)
                .where(Email.id.in_(email_ids))
            )
            result = await db.execute(stmt)
            emails = {str(e.id): e for e in result.scalars().all()}

            for search_result in results:
                email = emails.get(search_result.email_id)
                if email:
                    search_result.subject = email.subject
                    search_result.sender_email = email.sender_email
                    search_result.sender_name = email.sender_name
                    search_result.sent_date = email.sent_date
                    search_result.has_attachments = email.has_attachments
                    search_result.attachment_count = len(email.attachments) if email.attachments else 0
                    search_result.folder_path = email.folder_path
                    search_result.pst_file_id = str(email.pst_file_id)

        return results

    def _build_chroma_filters(self, filters: SearchFilters | None) -> dict[str, Any] | None:
        """Build ChromaDB where clause from filters."""
        if not filters:
            return None

        conditions: list[dict[str, Any]] = []

        if filters.pst_file_ids:
            if len(filters.pst_file_ids) == 1:
                conditions.append({"pst_file_id": filters.pst_file_ids[0]})
            else:
                conditions.append({
                    "$or": [{"pst_file_id": pid} for pid in filters.pst_file_ids]
                })

        if filters.sender_emails:
            if len(filters.sender_emails) == 1:
                conditions.append({"sender_email": filters.sender_emails[0]})
            else:
                conditions.append({
                    "$or": [{"sender_email": e} for e in filters.sender_emails]
                })

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    def _apply_sql_filters(self, stmt: Any, filters: SearchFilters) -> Any:
        """Apply SQL filters to a query statement."""
        conditions = []

        if filters.pst_file_ids:
            conditions.append(Email.pst_file_id.in_(filters.pst_file_ids))

        if filters.sender_emails:
            conditions.append(Email.sender_email.in_(filters.sender_emails))

        if filters.recipient_emails:
            # Check all recipient fields
            recipient_conditions = []
            for email in filters.recipient_emails:
                recipient_conditions.append(Email.to_recipients.contains([email]))
                recipient_conditions.append(Email.cc_recipients.contains([email]))
                recipient_conditions.append(Email.bcc_recipients.contains([email]))
            conditions.append(or_(*recipient_conditions))

        if filters.date_from:
            conditions.append(Email.sent_date >= filters.date_from)

        if filters.date_to:
            conditions.append(Email.sent_date <= filters.date_to)

        if filters.has_attachments is not None:
            conditions.append(Email.has_attachments == filters.has_attachments)

        if filters.folder_paths:
            folder_conditions = [
                Email.folder_path.like(f"{path}%") for path in filters.folder_paths
            ]
            conditions.append(or_(*folder_conditions))

        if filters.importance:
            conditions.append(Email.importance == filters.importance)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return stmt

    def _generate_snippet(self, text: str | None, query: str | None) -> str | None:
        """Generate a text snippet with search terms highlighted."""
        if not text:
            return None

        text = text[:1000]  # Limit text length

        if not query:
            return text[:200]

        # Find the first occurrence of any query term
        query_terms = query.lower().split()
        text_lower = text.lower()

        best_pos = len(text)
        for term in query_terms:
            pos = text_lower.find(term)
            if pos != -1 and pos < best_pos:
                best_pos = pos

        # Extract snippet around the best match
        if best_pos < len(text):
            start = max(0, best_pos - 50)
            end = min(len(text), best_pos + 150)
            snippet = text[start:end]

            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."

            return snippet

        return text[:200]

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse date string to datetime."""
        if not date_str:
            return None

        try:
            # Try ISO format first
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None


# Global instance
search_service = SearchService()


def get_search_service() -> SearchService:
    """Get the search service instance."""
    return search_service
