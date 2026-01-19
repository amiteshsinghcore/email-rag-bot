"""
RAG Service

Main service for Retrieval-Augmented Generation on email data.
"""

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from loguru import logger

from app.services.llm import (
    LLMFactory,
    LLMProvider,
    LLMProviderError,
    Message,
    StreamChunk,
)
from app.services.query_processor import (
    ProcessedQuery,
    QueryProcessor,
    QueryType,
    get_query_processor,
)
from app.services.retrieval_service import (
    RetrievalResult,
    RetrievalService,
    RetrievedDocument,
    get_retrieval_service,
)
from sqlalchemy import func, select
from app.db.models.email import Email
from app.db.models.processing_task import ProcessingTask, TaskStatus


@dataclass
class RAGResponse:
    """Response from RAG query."""

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    query_type: str = ""
    processed_query: dict[str, Any] | None = None
    model_used: str = ""
    provider_used: str = ""
    total_tokens: int = 0


@dataclass
class ChatMessage:
    """A message in a chat conversation."""

    role: str  # "user" or "assistant"
    content: str


class RAGService:
    """
    Service for RAG-based email question answering.

    Combines query processing, retrieval, and LLM generation
    for intelligent email analysis.
    """

    # System prompts for different query types
    SYSTEM_PROMPTS = {
        QueryType.FACTUAL: """You are an AI assistant analyzing email data. Answer questions factually and precisely.

OUTPUT FORMAT:
- Be CONCISE and DIRECT - get to the point immediately
- Use bullet points for lists
- Include specific email references (sender, date, subject) inline
- If information is missing, say so briefly

Example good response:
"John sent 5 emails about the project between Jan 1-15:
- Jan 3: Initial proposal (to: team@company.com)
- Jan 5: Budget revision (to: finance@company.com)
..."

Avoid lengthy explanations - users want quick, factual answers.""",

        QueryType.TEMPORAL: """You are an AI assistant analyzing email data with a focus on time/dates.

OUTPUT FORMAT:
- Present information CHRONOLOGICALLY in a clear timeline
- Use a structured format like:
  | Date | Sender | Subject | Key Action |
  |------|--------|---------|------------|
- Be CONCISE - one line per event
- Group by date ranges if there are many emails

Example:
"Timeline of project discussions:
| Date | From | Subject | Action |
|------|------|---------|--------|
| Jan 3 | John | Proposal | Initial submission |
| Jan 5 | Mary | Re: Proposal | Approved budget |
..."

Avoid prose - use structured timeline format.""",

        QueryType.TOPICAL: """You are an AI assistant analyzing email discussions on specific topics.

OUTPUT FORMAT:
- Start with a 1-2 sentence summary
- List key points as bullet points
- Include who said what (brief quotes if relevant)
- Group by subtopic if applicable

Example:
"**VPN Access Discussion** - 4 emails between Jan 3-10

Key Points:
- Jan 3: John requested VPN access for new team
- Jan 5: IT approved, sent credentials
- Jan 8: Issue reported - credentials not working
- Jan 10: Resolved - firewall rule updated

Participants: John, IT Team, Network Admin"

Be structured and scannable.""",

        QueryType.RELATIONAL: """You are an AI assistant analyzing communication patterns between people.

OUTPUT FORMAT:
- Start with a quick summary of the relationship/communication
- Use a table for email counts:
  | Person | Emails Sent | Main Topics |
- List key interactions briefly

Example:
"Communication between John and Mary: 12 emails over 2 weeks

| Direction | Count | Topics |
|-----------|-------|--------|
| John → Mary | 7 | Budget, Timeline |
| Mary → John | 5 | Approvals, Questions |

Key exchanges:
- Jan 3: Budget proposal discussion
- Jan 8: Timeline negotiation"

Be concise and data-focused.""",

        QueryType.SUMMARIZATION: """You are an AI assistant summarizing email content.

OUTPUT FORMAT:
- Start with a 2-3 sentence executive summary
- Use bullet points for key points
- Group by topic/theme if multiple subjects
- End with action items if any

Example:
"**Summary: Project Alpha Discussion (5 emails, Jan 3-10)**

Key Points:
- Budget approved at $50K
- Timeline: 3 months starting Feb 1
- Team: John (lead), Mary (support)

Action Items:
- [ ] John to send detailed plan by Jan 15
- [ ] Mary to confirm resource allocation"

Be structured and actionable.""",

        QueryType.ANALYTICAL: """You are an AI assistant providing email analytics and statistics.

OUTPUT FORMAT - USE TABLES AND NUMBERS:
- Present data in TABLES whenever possible
- Show rankings with counts
- Be precise with numbers
- Minimal prose - let the data speak

CRITICAL INSTRUCTION FOR GLOBAL COUNTS:
If the user asks for a TOTAL count or global statistics (e.g., "how many emails total?", "total inbox size"):
1. PRIORITIZE the "SYSTEM STATISTICS" provided at the top of the context.
2. The "Email Context" below contains only a SUBSET of emails (rag_top_k). DO NOT count them manually for global queries.
3. Only use the "Email Context" for specific filtering questions (e.g. "how many emails from John") if specific stats are missing.

Example for "How many emails total?":
"**Total Emails in System:**
| Category | Count |
|----------|-------|
| Total Emails | 489 |
| Total PST Files | 1 |"

Example for "Who emails me most?":
"**Top 10 Senders by Email Count:**
| Rank | Sender | Email Count | % of Total |
|------|--------|-------------|------------|
| 1 | john@company.com | 45 | 23% |
...
Total emails analyzed: 195"

ALWAYS use tables for rankings, counts, and comparisons. Be data-driven, not prose-heavy.""",

        QueryType.ATTACHMENT: """You are an AI assistant analyzing email attachments.

OUTPUT FORMAT:
- List attachments in a table format
- Include: filename, type, size (if available), sender, date

Example:
"**Attachments Found (3 files):**

| Filename | Type | From | Date | Email Subject |
|----------|------|------|------|---------------|
| proposal.pdf | PDF | John | Jan 3 | Project Proposal |
| budget.xlsx | Excel | Mary | Jan 5 | Budget Review |
| diagram.png | Image | John | Jan 8 | Architecture |

Note: 2 emails reference attachments that couldn't be extracted."

Be structured and informative.""",
    }

    DEFAULT_SYSTEM_PROMPT = """You are an AI assistant analyzing email data.

OUTPUT FORMAT RULES:
1. Be CONCISE - users want quick answers, not essays
2. Use TABLES for any data with counts, rankings, or comparisons
3. Use BULLET POINTS for lists
4. Start with the direct answer, then provide details
5. Include email references inline (sender, date)

For analytical questions (counts, rankings, "most/least", "how many"):
- ALWAYS use a table format
- Show top 10 by default for rankings
- Include counts and percentages

For factual questions:
- Answer directly first
- Then provide supporting details

Avoid:
- Long paragraphs of prose
- Repeating the question
- Unnecessary caveats and disclaimers
- Overly verbose explanations"""

    def __init__(
        self,
        query_processor: QueryProcessor | None = None,
        retrieval_service: RetrievalService | None = None,
    ) -> None:
        """Initialize RAG service."""
        self.query_processor = query_processor or get_query_processor()
        self.retrieval_service = retrieval_service or get_retrieval_service()

    async def query(
        self,
        question: str,
        chat_history: list[ChatMessage] | None = None,
        provider: str | None = None,
        model: str | None = None,
        pst_file_ids: list[str] | None = None,
        top_k: int = 10,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        include_sources: bool = True,
    ) -> RAGResponse:
        """
        Process a RAG query and return an answer.

        Args:
            question: User's question
            chat_history: Previous conversation messages
            provider: LLM provider to use
            model: Specific model to use
            pst_file_ids: Filter to specific PST files
            top_k: Number of documents to retrieve
            temperature: LLM temperature
            max_tokens: Maximum tokens to generate
            include_sources: Whether to include source citations

        Returns:
            RAGResponse with answer and metadata
        """
        logger.info(f"Processing RAG query: {question[:100]}...")

        # Process the query
        processed_query = await self.query_processor.process(question)
        
        # For simple analytical queries asking for global counts, bypass RAG and answer directly
        if processed_query.query_type == QueryType.ANALYTICAL:
            direct_answer = await self._try_direct_analytical_answer(question, processed_query)
            if direct_answer:
                return direct_answer

        # Retrieve relevant documents
        retrieval_result = await self.retrieval_service.retrieve_for_query_type(
            query=question,
            query_type=processed_query.query_type,
            processed_query=processed_query,
            top_k=top_k,
            pst_file_ids=pst_file_ids,
        )

        # Handle multi-query for complex queries
        if processed_query.sub_queries:
            additional_result = await self.retrieval_service.multi_query_retrieve(
                queries=processed_query.sub_queries,
                top_k_per_query=3,
                pst_file_ids=pst_file_ids,
            )
            # Merge results
            retrieval_result = self._merge_retrieval_results(
                retrieval_result,
                additional_result,
            )

        # Build context from retrieved documents
        stats_context = await self._get_global_stats_context()
        doc_context = self._build_context(retrieval_result.documents)
        context = f"{stats_context}\n\n{doc_context}"

        # Get provider settings from database (always fetch to get API key)
        provider_kwargs = {}
        from app.services.llm_settings_service import LLMSettingsService
        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            llm_settings_service = LLMSettingsService(db)
            default_setting = await llm_settings_service.get_default_settings()
            if default_setting:
                if provider is None:
                    provider = default_setting.provider
                # Handle "default" as a special value meaning "use the configured model"
                if (not model or model == "default") and default_setting.model:
                    model = default_setting.model
                if default_setting.api_key:
                    provider_kwargs["api_key"] = default_setting.api_key
                if default_setting.base_url:
                    provider_kwargs["base_url"] = default_setting.base_url
                logger.info(f"Using provider from database: {provider} with model {model}")

        # Get LLM provider
        try:
            llm = LLMFactory.get_provider(provider=provider, model=model, **provider_kwargs)
        except LLMProviderError as e:
            logger.error(f"Failed to get LLM provider: {e}")
            raise

        # Build messages
        messages = self._build_messages(
            question=question,
            context=context,
            query_type=processed_query.query_type,
            chat_history=chat_history,
        )

        # Generate response
        try:
            response = await llm.generate(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except LLMProviderError as e:
            logger.error(f"LLM generation failed: {e}")
            raise

        # Build source citations
        sources = []
        if include_sources:
            sources = self._build_sources(retrieval_result.documents)

        return RAGResponse(
            answer=response.content,
            sources=sources,
            query_type=processed_query.query_type.value,
            processed_query={
                "original": processed_query.original_query,
                "type": processed_query.query_type.value,
                "entities": processed_query.entities,
                "keywords": processed_query.keywords,
                "time_range": (
                    {
                        "start": processed_query.time_range.start.isoformat()
                        if processed_query.time_range and processed_query.time_range.start
                        else None,
                        "end": processed_query.time_range.end.isoformat()
                        if processed_query.time_range and processed_query.time_range.end
                        else None,
                    }
                    if processed_query.time_range
                    else None
                ),
            },
            model_used=response.model,
            provider_used=response.provider.value,
            total_tokens=response.usage.get("total_tokens", 0),
        )

    async def query_stream(
        self,
        question: str,
        chat_history: list[ChatMessage] | None = None,
        provider: str | None = None,
        model: str | None = None,
        pst_file_ids: list[str] | None = None,
        top_k: int = 10,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Process a RAG query and stream the response.

        Yields:
            String chunks of the response
        """
        logger.info(f"Processing streaming RAG query: {question[:100]}...")

        # Process the query
        processed_query = await self.query_processor.process(question)
        
        # For simple analytical queries asking for global counts, bypass RAG and answer directly
        if processed_query.query_type == QueryType.ANALYTICAL:
            direct_answer = await self._try_direct_analytical_answer(question, processed_query)
            if direct_answer:
                logger.info("Streaming direct DB answer")
                # Stream the answer immediately
                yield direct_answer.answer
                return

        # Retrieve relevant documents
        retrieval_result = await self.retrieval_service.retrieve_for_query_type(
            query=question,
            query_type=processed_query.query_type,
            processed_query=processed_query,
            top_k=top_k,
            pst_file_ids=pst_file_ids,
        )

        # Build context from retrieved documents
        stats_context = await self._get_global_stats_context()
        doc_context = self._build_context(retrieval_result.documents)
        context = f"{stats_context}\n\n{doc_context}"

        # Get provider settings from database (always fetch to get API key)
        provider_kwargs = {}
        from app.services.llm_settings_service import LLMSettingsService
        from app.db.session import async_session_factory

        async with async_session_factory() as db:
            llm_settings_service = LLMSettingsService(db)
            default_setting = await llm_settings_service.get_default_settings()
            if default_setting:
                if provider is None:
                    provider = default_setting.provider
                # Handle "default" as a special value meaning "use the configured model"
                if (not model or model == "default") and default_setting.model:
                    model = default_setting.model
                if default_setting.api_key:
                    provider_kwargs["api_key"] = default_setting.api_key
                if default_setting.base_url:
                    provider_kwargs["base_url"] = default_setting.base_url
                logger.info(f"Using provider from database: {provider} with model {model}")

        # Get LLM provider
        llm = LLMFactory.get_provider(provider=provider, model=model, **provider_kwargs)

        # Build messages
        messages = self._build_messages(
            question=question,
            context=context,
            query_type=processed_query.query_type,
            chat_history=chat_history,
        )

        # Stream response
        async for chunk in llm.generate_stream(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.content:
                yield chunk.content

    async def summarize_emails(
        self,
        email_ids: list[str] | None = None,
        pst_file_ids: list[str] | None = None,
        topic: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        max_emails: int = 50,
    ) -> RAGResponse:
        """
        Summarize a set of emails.

        Args:
            email_ids: Specific email IDs to summarize
            pst_file_ids: Filter to specific PST files
            topic: Focus summary on specific topic
            provider: LLM provider to use
            model: Model to use
            max_emails: Maximum emails to include

        Returns:
            RAGResponse with summary
        """
        # Build summary query
        if topic:
            query = f"Summarize all emails about: {topic}"
        else:
            query = "Provide a comprehensive summary of these emails"

        # Retrieve emails
        retrieval_result = await self.retrieval_service.retrieve(
            query=query,
            top_k=max_emails,
            pst_file_ids=pst_file_ids,
            use_hyde=False,  # Don't need HyDE for summarization
        )

        if not retrieval_result.documents:
            return RAGResponse(
                answer="No emails found to summarize.",
                sources=[],
                query_type=QueryType.SUMMARIZATION.value,
            )

        # Build context
        context = self._build_context(retrieval_result.documents)

        # Get LLM
        llm = LLMFactory.get_provider(provider=provider, model=model)

        # Summarization prompt
        summary_prompt = f"""Based on the following email context, provide a comprehensive summary.

{f'Focus on: {topic}' if topic else 'Include all major topics and themes.'}

Structure your summary with:
1. Overview (2-3 sentences)
2. Key Topics Discussed
3. Important Decisions or Action Items
4. Notable Participants

Email Context:
{context}

Summary:"""

        messages = [
            Message(
                role="system",
                content="You are an AI assistant that creates clear, structured summaries of email communications.",
            ),
            Message(role="user", content=summary_prompt),
        ]

        response = await llm.generate(
            messages=messages,
            temperature=0.5,  # Lower temperature for more focused summaries
            max_tokens=2048,
        )

        return RAGResponse(
            answer=response.content,
            sources=self._build_sources(retrieval_result.documents),
            query_type=QueryType.SUMMARIZATION.value,
            model_used=response.model,
            provider_used=response.provider.value,
            total_tokens=response.usage.get("total_tokens", 0),
        )

    async def _try_direct_analytical_answer(
        self, 
        question: str, 
        processed_query: ProcessedQuery
    ) -> RAGResponse | None:
        """
        Try to answer simple analytical queries directly from database without RAG.
        
        Returns RAGResponse if the query can be answered directly, None otherwise.
        """
        from app.db.session import async_session_factory
        
        question_lower = question.lower()
        
        # Patterns for simple global count questions
        global_count_patterns = [
            "how many emails",
            "total emails",
            "email count",
            "count of emails",
            "number of emails",
            "total inbox",
            "inbox size",
            "how many total",
        ]
        
        # Patterns for sender/recipient aggregation queries
        aggregation_patterns = [
            "who sends",
            "who sent",
            "who emails",
            "who emailed",
            "most emails from",
            "top senders",
            "sender sending",
            "frequent sender",
            "most frequent",
        ]
        
        # Check if this is asking for a simple global count
        is_global_count = any(pattern in question_lower for pattern in global_count_patterns)
        
        # Check if this is asking for sender/recipient aggregation
        is_aggregation = any(pattern in question_lower for pattern in aggregation_patterns)
        
        # Check if there are filtering keywords that require RAG (use word boundaries)
        import re
        content_filtering_keywords = ["about", "regarding", "concerning", "related to", "discussing", "mentioning"]
        has_content_filters = any(re.search(r'\b' + re.escape(keyword) + r'\b', question_lower) for keyword in content_filtering_keywords)
        
        # We can handle entity filters (senders) and time filters directly in DB for counts
        # But if it's about TOPIC, we need RAG
        logger.info(f"Direct DB query check: is_global_count={is_global_count}, is_aggregation={is_aggregation}, has_content_filters={has_content_filters}, entities={processed_query.entities}, question={question_lower}")
        
        # Only answer directly if it's an analytical query without specific content/topic filters
        if not (is_global_count or is_aggregation) or has_content_filters:
            return None
            
        # Get stats from database
        async with async_session_factory() as db:
            # Base query components
            filters = []
            
            # Apply entity filters if any (sender_email)
            email_entities = [e for e in processed_query.entities if "@" in e]
            if email_entities:
                filters.append(Email.sender_email.in_(email_entities))
            
            # Apply time range filters if any
            if processed_query.time_range:
                if processed_query.time_range.start:
                    filters.append(Email.sent_date >= processed_query.time_range.start)
                if processed_query.time_range.end:
                    filters.append(Email.sent_date <= processed_query.time_range.end)

            # Handle global count queries (possibly filtered by sender/time)
            if is_global_count and not is_aggregation:
                count_query = select(func.count(Email.id))
                if filters:
                    count_query = count_query.where(*filters)
                
                email_count_result = await db.execute(count_query)
                total_emails = email_count_result.scalar() or 0
                
                # PST count only makes sense for global unfiltered queries
                total_pst_files = 0
                if not filters:
                    pst_count_result = await db.execute(select(func.count(ProcessingTask.id)))
                    total_pst_files = pst_count_result.scalar() or 0
                
                logger.info(f"Answering count directly from DB: {total_emails} emails")
                
                filter_desc = ""
                if email_entities:
                    filter_desc += f" from {', '.join(email_entities)}"
                if processed_query.time_range:
                    filter_desc += f" in period '{processed_query.time_range.description or 'specified range'}'"

                if not filter_desc:
                    answer = f"""**Total Emails in System:**

| Category | Count |
|----------|-------|
| Total Emails | {total_emails} |
| Total PST Files | {total_pst_files} |

This is the complete count of all indexed emails in your system."""
                else:
                    answer = f"**Email Count Results:**\n\nThere are **{total_emails}** emails found{filter_desc}.\n\n(Counted from complete database dataset)"
            
            # Handle sender aggregation queries
            elif is_aggregation:
                # Query top senders
                sender_query = (
                    select(Email.sender_email, func.count(Email.id).label('email_count'))
                    .where(Email.sender_email.isnot(None))
                )
                
                if filters:
                    sender_query = sender_query.where(*filters)
                    
                sender_query = sender_query.group_by(Email.sender_email).order_by(func.count(Email.id).desc()).limit(20)
                
                result = await db.execute(sender_query)
                sender_counts = result.all()
                
                # Get total email count for percentage calculation
                count_query_total = select(func.count(Email.id))
                if filters:
                    count_query_total = count_query_total.where(*filters)
                
                total_count_result = await db.execute(count_query_total)
                total_emails = total_count_result.scalar() or 0
                
                logger.info(f"Answering sender aggregation from DB: {len(sender_counts)} senders, {total_emails} total emails")
                
                # Format as table
                table_rows = []
                for idx, (sender, count) in enumerate(sender_counts[:10], 1):
                    percentage = (count / total_emails * 100) if total_emails > 0 else 0
                    table_rows.append(f"| {idx} | {sender} | {count} | {percentage:.1f}% |")
                
                filter_desc = ""
                if email_entities:
                    filter_desc += f" for {', '.join(email_entities)}"
                if processed_query.time_range:
                    filter_desc += f" in period '{processed_query.time_range.description or 'specified range'}'"

                answer = f"""**Top 10 Senders by Email Count{filter_desc}:**

| Rank | Sender | Email Count | % of Total |
|------|--------|-------------|------------|
{chr(10).join(table_rows)}

**Total emails analyzed: {total_emails}** (complete dataset from database)"""
            
            else:
                return None
        
        return RAGResponse(
            answer=answer,
            sources=[],
            query_type=QueryType.ANALYTICAL.value,
            processed_query={
                "original": processed_query.original_query,
                "type": processed_query.query_type.value,
                "entities": [],
                "keywords": processed_query.keywords,
                "time_range": None,
            },
            model_used="direct_db_query",
            provider_used="system",
            total_tokens=0,
        )

    async def _get_global_stats_context(self) -> str:
        """Get global statistics for RAG context."""
        from app.db.session import async_session_factory
        
        async with async_session_factory() as db:
            # Count total emails
            email_count_result = await db.execute(select(func.count(Email.id)))
            total_emails = email_count_result.scalar() or 0
            
            # Count PST files
            pst_count_result = await db.execute(select(func.count(ProcessingTask.id)))
            total_pst_files = pst_count_result.scalar() or 0
            
            return f"SYSTEM STATISTICS:\n- Total Emails Indexed: {total_emails}\n- Total PST Files Processed: {total_pst_files}\n"

    def _build_context(
        self,
        documents: list[RetrievedDocument],
        max_context_length: int = 32000,
    ) -> str:
        """Build context string from retrieved documents."""
        if not documents:
            return "No relevant emails found in the database."

        context_parts = []
        current_length = 0

        for i, doc in enumerate(documents):
            # Build document representation
            metadata = doc.metadata
            doc_context = f"\n--- Email {i + 1} ---\n"

            if metadata.get("subject"):
                doc_context += f"Subject: {metadata['subject']}\n"
            if metadata.get("sender"):
                doc_context += f"From: {metadata['sender']}\n"
            if metadata.get("date"):
                # Convert timestamp to human-readable format (DD-Month-Year HH:MM)
                date_val = metadata["date"]
                if isinstance(date_val, (int, float)):
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(date_val, tz=timezone.utc)
                    formatted_date = dt.strftime("%d-%b-%Y %H:%M")
                else:
                    formatted_date = date_val
                doc_context += f"Date: {formatted_date}\n"

            doc_context += f"\nContent:\n{doc.content}\n"

            # Check length limit
            if current_length + len(doc_context) > max_context_length:
                break

            context_parts.append(doc_context)
            current_length += len(doc_context)

        return "\n".join(context_parts)

    def _build_messages(
        self,
        question: str,
        context: str,
        query_type: QueryType,
        chat_history: list[ChatMessage] | None = None,
    ) -> list[Message]:
        """Build message list for LLM."""
        # Get appropriate system prompt
        system_prompt = self.SYSTEM_PROMPTS.get(query_type, self.DEFAULT_SYSTEM_PROMPT)

        messages = [Message(role="system", content=system_prompt)]

        # Add chat history if present
        if chat_history:
            for msg in chat_history[-10:]:  # Limit history to last 10 messages
                messages.append(Message(role=msg.role, content=msg.content))

        # Build user message with context
        user_message = f"""Based on the following email context, answer my question.

Email Context:
{context}

Question: {question}

RESPONSE FORMAT REQUIREMENTS:
- For questions asking "who/what is the most/least" or rankings: USE A TABLE with Rank, Name, Count columns
- For counts/statistics: Show numbers clearly with a table
- For lists: Use bullet points
- For timelines: Use chronological table format
- Be CONCISE - avoid long paragraphs
- Start with the direct answer, then provide supporting details
- If data is missing, state it briefly"""

        messages.append(Message(role="user", content=user_message))

        return messages

    def _build_sources(
        self,
        documents: list[RetrievedDocument],
        max_sources: int = 10,
    ) -> list[dict[str, Any]]:
        """Build source citations from documents."""
        sources = []

        for doc in documents[:max_sources]:
            metadata = doc.metadata

            source = {
                "id": doc.id,
                "type": doc.source_type,
                "score": round(doc.rerank_score or doc.score, 4),
            }

            if metadata.get("email_id"):
                source["email_id"] = metadata["email_id"]
            if metadata.get("subject"):
                source["subject"] = metadata["subject"][:100]
            if metadata.get("sender"):
                source["sender"] = metadata["sender"]
            if metadata.get("date"):
                # Convert timestamp to ISO string if it's a float
                date_val = metadata["date"]
                if isinstance(date_val, (int, float)):
                    from datetime import datetime, timezone
                    source["date"] = datetime.fromtimestamp(date_val, tz=timezone.utc).isoformat()
                else:
                    source["date"] = date_val
            elif metadata.get("sent_date"):
                source["date"] = metadata["sent_date"]  # Fallback to ISO string if available
            if doc.source_type == "attachment" and metadata.get("filename"):
                source["filename"] = metadata["filename"]

            sources.append(source)

        return sources

    def _merge_retrieval_results(
        self,
        result1: RetrievalResult,
        result2: RetrievalResult,
    ) -> RetrievalResult:
        """Merge two retrieval results, deduplicating by ID."""
        seen_ids = {doc.id for doc in result1.documents}
        merged_docs = list(result1.documents)

        for doc in result2.documents:
            if doc.id not in seen_ids:
                merged_docs.append(doc)
                seen_ids.add(doc.id)

        # Re-sort by score
        merged_docs.sort(key=lambda x: x.rerank_score or x.score, reverse=True)

        return RetrievalResult(
            documents=merged_docs,
            query=result1.query,
            total_retrieved=len(merged_docs),
        )

    async def get_available_providers(self) -> list[dict[str, Any]]:
        """Get list of available LLM providers."""
        return LLMFactory.get_available_providers()


# Global instance
rag_service = RAGService()


def get_rag_service() -> RAGService:
    """Get the RAG service instance."""
    return rag_service
