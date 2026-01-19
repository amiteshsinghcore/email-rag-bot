"""
Query Processor Service

Handles query classification, enrichment, and preprocessing for RAG.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from app.services.llm import LLMFactory, Message, get_default_llm


async def get_llm_from_database():
    """Get LLM provider with settings from database."""
    from app.db.session import async_session_factory
    from app.services.llm_settings_service import LLMSettingsService

    try:
        async with async_session_factory() as db:
            llm_settings_service = LLMSettingsService(db)
            default_setting = await llm_settings_service.get_default_settings()
            if default_setting:
                kwargs = {}
                if default_setting.api_key:
                    kwargs["api_key"] = default_setting.api_key
                if default_setting.base_url:
                    kwargs["base_url"] = default_setting.base_url
                return LLMFactory.get_provider(
                    provider=default_setting.provider,
                    model=default_setting.model,
                    **kwargs
                )
    except Exception as e:
        logger.warning(f"Failed to get LLM from database: {e}")

    # Fallback to environment-based default
    return get_default_llm()


class QueryType(str, Enum):
    """Types of queries the system can handle."""

    FACTUAL = "factual"  # Who sent email X? What was discussed?
    TEMPORAL = "temporal"  # Emails from last week, between dates
    TOPICAL = "topical"  # Emails about project Y
    RELATIONAL = "relational"  # Conversations between A and B
    SUMMARIZATION = "summarization"  # Summarize emails about X
    ANALYTICAL = "analytical"  # How many emails? Most frequent sender?
    ATTACHMENT = "attachment"  # Find emails with PDFs, specific attachments


@dataclass
class TimeRange:
    """Represents a time range extracted from a query."""

    start: datetime | None = None
    end: datetime | None = None
    description: str = ""


@dataclass
class ProcessedQuery:
    """Result of query processing."""

    original_query: str
    processed_query: str
    query_type: QueryType
    time_range: TimeRange | None = None
    entities: list[str] = field(default_factory=list)  # Extracted names, emails
    keywords: list[str] = field(default_factory=list)  # Important terms
    expanded_terms: list[str] = field(default_factory=list)  # Abbreviation expansions
    sub_queries: list[str] = field(default_factory=list)  # Multi-query decomposition
    hyde_document: str | None = None  # Hypothetical document for HyDE
    metadata_filters: dict[str, Any] = field(default_factory=dict)


class QueryProcessor:
    """
    Processes and enriches user queries for better retrieval.

    Features:
    - Query classification (7 types)
    - Entity extraction (names, emails, dates)
    - Abbreviation expansion
    - Time expression parsing
    - Multi-query generation
    - HyDE (Hypothetical Document Embeddings)
    """

    # Common email-related abbreviations
    ABBREVIATIONS = {
        "re:": "reply to",
        "fwd:": "forward",
        "fw:": "forward",
        "cc": "carbon copy",
        "bcc": "blind carbon copy",
        "asap": "as soon as possible",
        "fyi": "for your information",
        "eod": "end of day",
        "eow": "end of week",
        "wfh": "work from home",
        "ooo": "out of office",
        "pto": "paid time off",
        "mtg": "meeting",
        "pls": "please",
        "thx": "thanks",
        "tbd": "to be determined",
        "tbc": "to be confirmed",
        "eta": "estimated time of arrival",
        "q1": "first quarter",
        "q2": "second quarter",
        "q3": "third quarter",
        "q4": "fourth quarter",
        "fy": "fiscal year",
        "yoy": "year over year",
        "mom": "month over month",
    }

    # Patterns for query type classification
    QUERY_TYPE_PATTERNS = {
        QueryType.TEMPORAL: [
            r"\b(yesterday|today|last\s+week|last\s+month|this\s+week|this\s+month)\b",
            r"\b(before|after|between|during|since|until)\b.*\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4})\b",
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
        ],
        QueryType.RELATIONAL: [
            r"\b(between|from|to)\s+\w+\s+(and|to)\s+\w+\b",
            r"\b(conversation|thread|discussion)\s+(with|between)\b",
            r"\b(exchanged|sent\s+to|received\s+from)\b",
        ],
        QueryType.SUMMARIZATION: [
            r"\b(summarize|summary|overview|brief|recap)\b",
            r"\b(main\s+points|key\s+takeaways|highlights)\b",
        ],
        QueryType.ANALYTICAL: [
            r"\b(how\s+many|count|number\s+of|total)\b",
            r"\b(most|least|top|bottom|average|frequent)\b",
            r"\b(statistics|stats|metrics|analysis)\b",
        ],
        QueryType.ATTACHMENT: [
            r"\b(attachment|attached|file|document|pdf|excel|word|spreadsheet)\b",
            r"\b(with\s+files?|has\s+attachment)\b",
        ],
        QueryType.TOPICAL: [
            r"\b(about|regarding|concerning|related\s+to|on\s+the\s+topic)\b",
            r"\b(project|meeting|discussion|report|proposal)\b",
        ],
        QueryType.FACTUAL: [
            r"^(who|what|when|where|which|did)\b",
            r"\b(sender|recipient|subject|sent|received)\b",
        ],
    }

    # Time expression patterns
    TIME_PATTERNS = [
        (r"\byesterday\b", lambda: (datetime.now().replace(hour=0, minute=0, second=0), None)),
        (r"\btoday\b", lambda: (datetime.now().replace(hour=0, minute=0, second=0), None)),
        (r"\blast\s+week\b", lambda: _relative_time_range(weeks=-1)),
        (r"\blast\s+month\b", lambda: _relative_time_range(months=-1)),
        (r"\blast\s+(\d+)\s+days?\b", lambda m: _relative_time_range(days=-int(m.group(1)))),
        (r"\bthis\s+week\b", lambda: _week_range(current=True)),
        (r"\bthis\s+month\b", lambda: _month_range(current=True)),
    ]

    def __init__(self, use_llm: bool = True) -> None:
        """
        Initialize query processor.

        Args:
            use_llm: Whether to use LLM for advanced processing (HyDE, multi-query)
        """
        self.use_llm = use_llm

    async def process(self, query: str) -> ProcessedQuery:
        """
        Process and enrich a user query.

        Args:
            query: Raw user query

        Returns:
            ProcessedQuery with all enrichments
        """
        logger.debug(f"Processing query: {query}")

        # Basic processing
        processed_query = self._normalize_query(query)
        
        # Try LLM classification first if enabled
        query_type = None
        if self.use_llm:
            query_type = await self._classify_query_with_llm(query)
            
        # Fallback to pattern-based classification
        if not query_type:
            query_type = self._classify_query(query)
            
        time_range = self._extract_time_range(query)
        entities = self._extract_entities(query)
        keywords = self._extract_keywords(query)
        expanded_terms = self._expand_abbreviations(query)

        result = ProcessedQuery(
            original_query=query,
            processed_query=processed_query,
            query_type=query_type,
            time_range=time_range,
            entities=entities,
            keywords=keywords,
            expanded_terms=expanded_terms,
        )

        # LLM-based enrichment
        if self.use_llm:
            try:
                # Generate sub-queries for complex queries
                if query_type in [QueryType.ANALYTICAL, QueryType.SUMMARIZATION]:
                    result.sub_queries = await self._generate_sub_queries(query)

                # Generate HyDE document for semantic search improvement
                # Only use HyDE for search-heavy types, not analytical/factual where exact match matters more
                if query_type not in [QueryType.ANALYTICAL]:
                    result.hyde_document = await self._generate_hyde_document(query, query_type)
            except Exception as e:
                logger.warning(f"LLM enrichment failed: {e}")

        # Build metadata filters based on extracted information
        result.metadata_filters = self._build_metadata_filters(result)

        logger.debug(f"Query classified as {query_type}, entities: {entities}")
        return result

    async def _classify_query_with_llm(self, query: str) -> QueryType | None:
        """Classify query using LLM."""
        try:
            llm = await get_llm_from_database()

            prompt = f"""Classify the following email search query into exactly one of these categories:

1. factual (Specific questions: who, what, when, where)
2. temporal (Time-based: emails from last week, dates)
3. topical (Topic-based: about project X, regarding Y)
4. relational (Between people: emails between John and Mary)
5. summarization (Summarize threads, key points)
6. analytical (Counts, stats, most frequent, trends)
7. attachment (Files, PDFs, specific attachments)

Query: "{query}"

Return ONLY the category name (lowercase)."""

            response = await llm.generate(
                messages=[
                    Message(role="system", content="You are a precise query classifier."),
                    Message(role="user", content=prompt),
                ],
                temperature=0.1,
                max_tokens=20,
            )

            category = response.content.strip().lower()
            
            # Remove any numbering or extra text
            if "." in category:
                category = category.split(".")[-1].strip()

            # Match against Enum values
            for qt in QueryType:
                if qt.value == category:
                    return qt

            # Smart fallback for partial matches
            if "analysis" in category or "stat" in category:
                return QueryType.ANALYTICAL
            if "summary" in category:
                return QueryType.SUMMARIZATION
            if "time" in category or "date" in category:
                return QueryType.TEMPORAL
            if "attach" in category or "file" in category:
                return QueryType.ATTACHMENT

            return None

        except Exception as e:
            logger.warning(f"LLM classification failed: {e}")
            return None

    def _normalize_query(self, query: str) -> str:
        """Normalize query text."""
        # Remove extra whitespace
        query = " ".join(query.split())
        # Lowercase for matching (preserve original for display)
        return query.strip()

    def _classify_query(self, query: str) -> QueryType:
        """Classify the query type based on patterns."""
        query_lower = query.lower()

        # Check each query type's patterns
        for query_type, patterns in self.QUERY_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return query_type

        # Default to factual
        return QueryType.FACTUAL

    def _extract_time_range(self, query: str) -> TimeRange | None:
        """Extract time range from query."""
        query_lower = query.lower()

        for pattern, handler in self.TIME_PATTERNS:
            match = re.search(pattern, query_lower)
            if match:
                try:
                    if callable(handler):
                        # Check if handler needs match argument
                        import inspect

                        sig = inspect.signature(handler)
                        if sig.parameters:
                            start, end = handler(match)
                        else:
                            start, end = handler()
                        return TimeRange(
                            start=start,
                            end=end or datetime.now(),
                            description=match.group(0),
                        )
                except Exception as e:
                    logger.warning(f"Time extraction failed for pattern {pattern}: {e}")

        return None

    def _extract_entities(self, query: str) -> list[str]:
        """Extract named entities (emails, names) from query."""
        entities = []

        # Extract email addresses
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        entities.extend(re.findall(email_pattern, query))

        # Extract quoted strings (likely names or subjects)
        quoted_pattern = r'"([^"]+)"'
        entities.extend(re.findall(quoted_pattern, query))

        # Extract capitalized words that might be names (simple heuristic)
        words = query.split()
        for i, word in enumerate(words):
            if word[0].isupper() and word.lower() not in self._get_common_words():
                # Skip first word of sentence and common terms
                if i > 0 and not words[i - 1].endswith((".", "?", "!")):
                    entities.append(word)

        return list(set(entities))

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract important keywords from query."""
        # Remove stop words and extract significant terms
        stop_words = self._get_stop_words()
        words = re.findall(r"\b\w+\b", query.lower())
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return list(set(keywords))

    def _expand_abbreviations(self, query: str) -> list[str]:
        """Expand common email abbreviations."""
        expanded = []
        query_lower = query.lower()

        for abbr, expansion in self.ABBREVIATIONS.items():
            if abbr in query_lower:
                expanded.append(f"{abbr} ({expansion})")

        return expanded

    async def _generate_sub_queries(self, query: str) -> list[str]:
        """Generate sub-queries for complex queries using LLM."""
        try:
            llm = await get_llm_from_database()

            prompt = f"""Break down this email search query into 2-4 simpler sub-queries that would help find relevant emails.
Return only the sub-queries, one per line.

Original query: {query}

Sub-queries:"""

            response = await llm.generate(
                messages=[
                    Message(
                        role="system",
                        content="You are a helpful assistant that breaks down complex search queries into simpler components.",
                    ),
                    Message(role="user", content=prompt),
                ],
                temperature=0.3,
                max_tokens=200,
            )

            # Parse sub-queries from response
            sub_queries = [
                line.strip().lstrip("- •1234567890.")
                for line in response.content.split("\n")
                if line.strip() and not line.strip().startswith("Sub-queries")
            ]

            return sub_queries[:4]  # Limit to 4 sub-queries

        except Exception as e:
            logger.warning(f"Sub-query generation failed: {e}")
            return []

    async def _generate_hyde_document(self, query: str, query_type: QueryType) -> str | None:
        """
        Generate a hypothetical document for HyDE (Hypothetical Document Embeddings).

        HyDE improves retrieval by embedding a hypothetical answer instead of the query.
        """
        try:
            llm = await get_llm_from_database()

            type_prompts = {
                QueryType.FACTUAL: "Write a brief email excerpt that would answer this question",
                QueryType.TEMPORAL: "Write a brief email from the time period mentioned that would be relevant",
                QueryType.TOPICAL: "Write a brief email about this topic",
                QueryType.RELATIONAL: "Write a brief email exchange snippet between the mentioned parties",
                QueryType.SUMMARIZATION: "Write a brief email that would be included in this summary",
                QueryType.ANALYTICAL: "Write a brief email that would be counted in this analysis",
                QueryType.ATTACHMENT: "Write a brief email that would have the type of attachment mentioned",
            }

            prompt = f"""{type_prompts.get(query_type, "Write a brief email excerpt")} based on: {query}

Write only the hypothetical email content (2-3 sentences), nothing else."""

            response = await llm.generate(
                messages=[
                    Message(
                        role="system",
                        content="You generate realistic email excerpts for search optimization. Be concise.",
                    ),
                    Message(role="user", content=prompt),
                ],
                temperature=0.7,
                max_tokens=150,
            )

            return response.content.strip()

        except Exception as e:
            logger.warning(f"HyDE generation failed: {e}")
            return None

    def _build_metadata_filters(self, processed: ProcessedQuery) -> dict[str, Any]:
        """Build metadata filters for vector search based on extracted information."""
        filters = {}

        # Add time range filter - use Unix timestamps for ChromaDB compatibility
        if processed.time_range:
            if processed.time_range.start:
                filters["date_gte"] = processed.time_range.start.timestamp()
            if processed.time_range.end:
                filters["date_lte"] = processed.time_range.end.timestamp()

        # Add entity filters (sender/recipient)
        email_entities = [e for e in processed.entities if "@" in e]
        if email_entities:
            filters["participants"] = email_entities

        return filters

    @staticmethod
    def _get_stop_words() -> set[str]:
        """Get common English stop words."""
        return {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "this", "that", "these", "those", "i", "you", "he", "she", "it",
            "we", "they", "what", "which", "who", "whom", "whose", "where",
            "when", "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "not", "only", "same", "so",
            "than", "too", "very", "just", "also", "now", "here", "there",
            "emails", "email", "find", "search", "show", "get", "me",
        }

    @staticmethod
    def _get_common_words() -> set[str]:
        """Get common words that shouldn't be treated as entities."""
        return {
            "email", "emails", "message", "messages", "sent", "received",
            "from", "to", "subject", "about", "regarding", "concerning",
            "the", "a", "an", "and", "or", "but", "find", "search", "show",
            "all", "any", "some", "with", "without", "has", "have", "had",
        }


# Helper functions for time range calculation
def _relative_time_range(
    days: int = 0,
    weeks: int = 0,
    months: int = 0,
) -> tuple[datetime, datetime]:
    """Calculate relative time range from now."""
    from datetime import timedelta

    end = datetime.now()
    total_days = days + (weeks * 7) + (months * 30)
    start = end + timedelta(days=total_days)
    return (start, end)


def _week_range(current: bool = True) -> tuple[datetime, datetime]:
    """Get current or previous week range."""
    from datetime import timedelta

    now = datetime.now()
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    if current:
        return (start_of_week, now)
    else:
        return (start_of_week - timedelta(days=7), start_of_week)


def _month_range(current: bool = True) -> tuple[datetime, datetime]:
    """Get current or previous month range."""
    now = datetime.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    if current:
        return (start_of_month, now)
    else:
        # Previous month
        if now.month == 1:
            prev_month_start = now.replace(year=now.year - 1, month=12, day=1)
        else:
            prev_month_start = now.replace(month=now.month - 1, day=1)
        return (prev_month_start, start_of_month)


# Global instance
query_processor = QueryProcessor()


def get_query_processor() -> QueryProcessor:
    """Get the query processor instance."""
    return query_processor
