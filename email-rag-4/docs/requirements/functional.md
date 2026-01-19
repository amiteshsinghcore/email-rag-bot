# Functional Requirements

## FR1: PST File Processing

### FR1.1 File Upload
- Support PST file uploads up to 50GB (typical: 10GB)
- Drag-and-drop file upload via web UI
- Multiple PST file upload in a single session
- Validate PST file format before processing

### FR1.2 Email Extraction
- Extract all emails with complete metadata:
  - Subject, sender, recipients (To, CC, BCC)
  - Date sent, date received
  - Message ID, thread ID, In-Reply-To, References
  - Folder path within PST
  - Read/unread status
  - Importance/priority flags

### FR1.3 Attachment Processing
- Extract all attachments from emails
- Support parsing of:
  - PDF documents
  - Microsoft Word documents (.doc, .docx)
  - Microsoft Excel spreadsheets (.xls, .xlsx)
  - Plain text files (.txt)
  - Image files (for metadata extraction)
- Calculate MD5 and SHA-256 hashes for all attachments
- Extract text content for searchable indexing

### FR1.4 Embedding Generation
- Generate vector embeddings for all email content
- Use sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
- Batch processing: 256 chunks per batch
- Store embeddings in ChromaDB with metadata
- Support incremental embedding updates

### FR1.5 Progress Tracking
- Display real-time processing progress:
  - Overall percentage complete
  - Current phase (parsing, extracting, embedding, indexing)
  - Emails processed / total emails
  - Estimated time remaining (ETA)
- WebSocket-based updates for live UI refresh

### FR1.6 Error Handling
- Graceful handling of corrupted emails
- Skip problematic emails without stopping processing
- Log all errors with context for debugging
- Support resumable processing after failure
- Exponential backoff for transient errors

---

## FR2: Intelligent Query Engine

### FR2.1 Query Types (7 Types)

| Type | Description | Example |
|------|-------------|---------|
| **Simple Lookup** | Keyword-based search | "emails from John about budget" |
| **Summarization** | Thread summaries, key points | "summarize the project discussion" |
| **Chronological** | Thread reconstruction, timeline | "show the conversation history about Q4 planning" |
| **Analytical** | Counts, aggregations, statistics | "how many emails did I receive from marketing last month?" |
| **Comparative** | Side-by-side comparisons | "compare what John and Mary said about the proposal" |
| **Trend Analysis** | Time-series patterns | "how has communication volume changed over the quarter?" |
| **Entity Extraction** | Action items, decisions, people | "what decisions were made in the board meeting emails?" |

### FR2.2 Query Enrichment

#### Abbreviation Expansion
- Expand common abbreviations (ASAP, FYI, EOD, etc.)
- Context-aware expansion based on domain

#### Query Variation Generation
- Generate multiple query variations for better recall
- Synonym expansion
- Phrase reformulation

#### Time Reference Extraction
- Parse natural language time references:
  - "last week" -> date range
  - "yesterday" -> specific date
  - "Q4 2024" -> date range
  - "since the meeting" -> context-based date

#### Hypothetical Document Embeddings (HyDE)
- Generate hypothetical answer for better retrieval
- Use LLM to create ideal document representation

### FR2.3 Automatic Relationship Discovery

- **Find Related Conversations**: Surface emails in the same thread or topic
- **Detect Contradictions**: Identify conflicting statements across emails
- **Track Decision Evolution**: Show how decisions changed over time
- **Identify Missing Items**: Flag referenced emails/attachments that don't exist

---

## FR3: Search & Retrieval

### FR3.1 Semantic Search
- Vector similarity search using ChromaDB
- Cosine similarity scoring
- Top-K result retrieval with configurable K

### FR3.2 Metadata Filtering
- Filter by sender/recipient email address
- Filter by date range (from/to)
- Filter by folder path
- Filter by attachment presence
- Filter by importance/priority
- Combine multiple filters with AND/OR logic

### FR3.3 Full-Text Search
- PostgreSQL full-text search on subject and body
- Support for Boolean operators (AND, OR, NOT)
- Phrase matching with quotes
- Wildcard support

### FR3.4 Thread Reconstruction
- Reconstruct email threads using Message-ID and References
- Display chronological thread view
- Show thread participants
- Highlight thread entry point

### FR3.5 Source Citations
- Return source email IDs with each result
- Include relevance scores
- Provide snippet with context highlighting
- Link to full email view

---

## FR4: Forensic & Investigation Features

### FR4.1 Evidence Integrity
- Calculate SHA-256 hash on PST file import
- Store hash for verification
- Detect any modifications to source data
- Immutable audit log of all operations

### FR4.2 Audit Logging
- Log all user actions with timestamps
- Track search queries and results viewed
- Record email access events
- Export audit logs for compliance

### FR4.3 Email Header Analysis
- Extract full routing path (Received headers)
- Parse SPF/DKIM/DMARC results
- Detect spoofing indicators
- Identify originating IP addresses

### FR4.4 Timeline Analysis
- Build chronological timelines of communications
- Detect gaps in communication (potential deleted emails)
- Identify unusual activity patterns (time of day, frequency)
- Visualize activity heatmaps

### FR4.5 Network Graph Analysis
- Visualize communication networks
- Identify key players:
  - Hubs (high connectivity)
  - Bridges (connecting groups)
  - Influencers (high message volume)
- Detect cliques and groups
- Export network data

### FR4.6 Legal Discovery Support
- Attorney-client privilege detection (keyword/pattern based)
- PII scanning (SSN, credit card numbers, phone numbers)
- Export evidence packages with chain of custody documentation
- Bates numbering support for document production

---

## FR5: Multi-LLM Support

### FR5.1 Custom LLM Endpoints
- Support any OpenAI-compatible API endpoint
- Configurable base URL and API key
- Custom model selection

### FR5.2 OpenAI Integration
- Support GPT-4, GPT-4-Turbo
- Support GPT-3.5-Turbo
- Streaming response support
- Function calling support

### FR5.3 Anthropic Claude Integration
- Support Claude 3 (Opus, Sonnet, Haiku)
- Support Claude 2.1
- Streaming response support

### FR5.4 Google Gemini Integration
- Support Gemini Pro
- Support Gemini Ultra (when available)
- Streaming response support

### FR5.5 xAI Grok Integration
- Support Grok models
- API integration

### FR5.6 Provider Switching
- Switch LLM providers via settings UI
- Per-query provider selection
- Fallback provider configuration
- API key management per provider

---

## FR6: User Interface

### FR6.1 File Upload Interface
- Drag-and-drop zone for PST files
- File size and type validation
- Upload queue management
- Cancel/retry upload support

### FR6.2 Processing Progress Display
- Real-time progress bar
- Current phase indicator
- Emails processed counter
- ETA display
- Error notifications

### FR6.3 Chat Interface
- Conversational query input
- Message history display
- Context-aware follow-up questions
- Clear/reset conversation

### FR6.4 Streaming Responses
- Character-by-character response streaming
- Claude Code-style activity display
- Show "thinking" indicator
- Progressive rendering of results

### FR6.5 Activity Display
- Show system operations in real-time
- Display query enrichment steps
- Show retrieval process
- Visualize LLM reasoning

### FR6.6 Settings Panel
- LLM provider configuration
- API key management
- Model selection
- Response preferences (temperature, length)

### FR6.7 Forensic Dashboard
- Evidence integrity status
- Timeline visualization
- Network graph viewer
- Audit log viewer
- Export controls
