# Database Design

## Overview

The system uses a **hybrid database architecture** for optimal performance:

1. **PostgreSQL** - Structured metadata and analytics
2. **ChromaDB** - Vector embeddings for semantic search
3. **Redis** - Caching and real-time events

## Why This Hybrid Approach?

| Database | Purpose | Strength |
|----------|---------|----------|
| **PostgreSQL** | Email metadata, forensics | Fast analytical queries, full-text search, JSON support |
| **ChromaDB** | Email content embeddings | Semantic similarity search, vector operations |
| **Redis** | Activity events, cache | Real-time pub/sub, fast in-memory operations |

---

## PostgreSQL Schema

### Tables

#### 1. `emails`
Core email metadata for fast analytical queries.

```sql
CREATE TABLE emails (
    id UUID PRIMARY KEY,
    message_id TEXT UNIQUE NOT NULL,
    thread_id TEXT,
    in_reply_to TEXT,
    references TEXT[],

    -- Headers
    subject TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipients TEXT[] NOT NULL,
    cc TEXT[],
    bcc TEXT[],
    reply_to TEXT,

    -- Timestamps
    date TIMESTAMP NOT NULL,
    received_timestamps JSONB,

    -- Content
    body_plain TEXT,
    body_html TEXT,
    body_preview TEXT,  -- First 500 chars for quick view

    -- Metadata
    folder TEXT,
    has_attachments BOOLEAN DEFAULT FALSE,
    attachment_count INTEGER DEFAULT 0,
    word_count INTEGER,
    language TEXT,

    -- Forensics
    raw_headers TEXT,
    spf_result TEXT,
    dkim_result TEXT,
    dmarc_result TEXT,
    originating_ip INET,

    -- Processing
    processed_at TIMESTAMP DEFAULT NOW(),
    embedding_created BOOLEAN DEFAULT FALSE,

    -- Full-text search
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(subject, '') || ' ' || coalesce(body_plain, ''))
    ) STORED,

    CONSTRAINT valid_sender CHECK (sender ~ '^[^@]+@[^@]+$')
);

-- Indexes for performance
CREATE INDEX idx_emails_sender ON emails(sender);
CREATE INDEX idx_emails_date ON emails(date DESC);
CREATE INDEX idx_emails_thread ON emails(thread_id);
CREATE INDEX idx_emails_message_id ON emails(message_id);
CREATE INDEX idx_emails_folder ON emails(folder);
CREATE INDEX idx_emails_has_attachments ON emails(has_attachments) WHERE has_attachments = true;
CREATE INDEX idx_emails_search ON emails USING GIN(search_vector);

-- Composite indexes for common queries
CREATE INDEX idx_emails_sender_date ON emails(sender, date DESC);
CREATE INDEX idx_emails_thread_date ON emails(thread_id, date ASC);
```

#### 2. `attachments`
Attachment metadata and extracted content.

```sql
CREATE TABLE attachments (
    id UUID PRIMARY KEY,
    email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,

    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,

    -- Extracted content
    extracted_text TEXT,
    extraction_status TEXT CHECK (extraction_status IN ('pending', 'success', 'failed', 'unsupported')),
    extraction_error TEXT,

    -- Hashes for deduplication
    md5_hash TEXT,
    sha256_hash TEXT,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(email_id, filename)
);

CREATE INDEX idx_attachments_email ON attachments(email_id);
CREATE INDEX idx_attachments_sha256 ON attachments(sha256_hash);
CREATE INDEX idx_attachments_type ON attachments(content_type);
```

#### 3. `email_chunks`
Links between emails and their vector chunks in ChromaDB.

```sql
CREATE TABLE email_chunks (
    id UUID PRIMARY KEY,
    email_id UUID NOT NULL REFERENCES emails(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,

    chunk_text TEXT NOT NULL,
    chunk_type TEXT CHECK (chunk_type IN ('body', 'attachment', 'combined')),

    -- Reference to ChromaDB
    chromadb_id TEXT NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(email_id, chunk_index)
);

CREATE INDEX idx_chunks_email ON email_chunks(email_id);
CREATE INDEX idx_chunks_chromadb ON email_chunks(chromadb_id);
```

#### 4. `evidence` (Forensic)
Chain of custody for legal compliance.

```sql
CREATE TABLE evidence (
    id UUID PRIMARY KEY,
    case_id TEXT NOT NULL,

    pst_filename TEXT NOT NULL,
    pst_sha256 TEXT NOT NULL UNIQUE,
    pst_size_bytes BIGINT NOT NULL,

    registered_by TEXT NOT NULL,
    registered_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Chain of custody log
    custody_log JSONB NOT NULL DEFAULT '[]',

    -- Status
    status TEXT CHECK (status IN ('active', 'archived', 'exported')) DEFAULT 'active',

    metadata JSONB
);

CREATE INDEX idx_evidence_case ON evidence(case_id);
CREATE INDEX idx_evidence_sha256 ON evidence(pst_sha256);
```

#### 5. `processing_tasks`
Track PST processing jobs.

```sql
CREATE TABLE processing_tasks (
    id UUID PRIMARY KEY,
    evidence_id UUID REFERENCES evidence(id),

    status TEXT CHECK (status IN ('pending', 'running', 'completed', 'failed')) NOT NULL,
    current_phase TEXT,

    emails_total INTEGER DEFAULT 0,
    emails_processed INTEGER DEFAULT 0,
    attachments_processed INTEGER DEFAULT 0,
    chunks_created INTEGER DEFAULT 0,

    errors JSONB DEFAULT '[]',

    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    metadata JSONB
);

CREATE INDEX idx_tasks_status ON processing_tasks(status);
CREATE INDEX idx_tasks_evidence ON processing_tasks(evidence_id);
```

---

## ChromaDB Collections

### Collection: `email_chunks`

Stores vector embeddings of email content.

```python
collection = client.create_collection(
    name="email_chunks",
    metadata={
        "hnsw:space": "cosine",
        "description": "Email content embeddings"
    }
)

# Document structure
{
    "id": "email_uuid_chunk_0",
    "embedding": [0.123, 0.456, ...],  # 384-dim vector
    "document": "Email text chunk...",
    "metadata": {
        "email_id": "uuid",
        "sender": "user@example.com",
        "subject": "Meeting notes",
        "date": "2024-01-15T10:30:00",
        "thread_id": "thread_uuid",
        "chunk_index": 0,
        "chunk_type": "body"
    }
}
```

### Metadata Filters

ChromaDB supports filtering on metadata:

```python
# Find emails from specific sender
results = collection.query(
    query_embeddings=[query_vector],
    where={"sender": "john@company.com"},
    n_results=10
)

# Find emails in date range
results = collection.query(
    query_embeddings=[query_vector],
    where={
        "$and": [
            {"date": {"$gte": "2024-01-01"}},
            {"date": {"$lte": "2024-01-31"}}
        ]
    },
    n_results=10
)
```

---

## Redis Data Structures

### 1. Processing Status

```redis
# Hash for task status
HSET task:{task_id}:status
    status "running"
    phase "embedding"
    emails_processed "5000"
    emails_total "10000"
    progress "50.0"
```

### 2. Activity Events (Pub/Sub)

```redis
# Publish activity events
PUBLISH activity_events '{
    "type": "query_enriched",
    "message": "Query enhanced with 4 variations",
    "timestamp": "2024-01-15T10:30:00"
}'
```

### 3. Caching

```redis
# Cache frequently accessed emails
SETEX email:{email_id} 3600 '{...email data...}'

# Cache query results
SETEX query:hash:{query_hash} 300 '{...results...}'
```

---

## Analytical Queries Examples

### 1. Top Senders by Volume

```sql
SELECT
    sender,
    COUNT(*) as email_count,
    COUNT(DISTINCT thread_id) as thread_count,
    MIN(date) as first_email,
    MAX(date) as last_email
FROM emails
WHERE date >= NOW() - INTERVAL '30 days'
GROUP BY sender
ORDER BY email_count DESC
LIMIT 20;
```

### 2. Communication Network

```sql
WITH email_pairs AS (
    SELECT
        sender,
        unnest(recipients) as recipient,
        COUNT(*) as interaction_count
    FROM emails
    GROUP BY sender, recipient
)
SELECT * FROM email_pairs
WHERE interaction_count > 5
ORDER BY interaction_count DESC;
```

### 3. Thread Analysis

```sql
SELECT
    thread_id,
    MIN(subject) as subject,
    COUNT(*) as email_count,
    COUNT(DISTINCT sender) as participant_count,
    MIN(date) as thread_start,
    MAX(date) as thread_end,
    MAX(date) - MIN(date) as thread_duration
FROM emails
WHERE thread_id IS NOT NULL
GROUP BY thread_id
HAVING COUNT(*) > 1
ORDER BY email_count DESC
LIMIT 50;
```

### 4. Deleted Email Detection

```sql
WITH referenced_ids AS (
    SELECT DISTINCT unnest(references) as ref_id
    FROM emails
)
SELECT ref_id
FROM referenced_ids
WHERE ref_id NOT IN (SELECT message_id FROM emails);
```

### 5. Full-Text Search

```sql
SELECT
    id,
    subject,
    sender,
    date,
    ts_rank(search_vector, query) AS rank
FROM emails,
     to_tsquery('english', 'budget & (approval | approved)') query
WHERE search_vector @@ query
ORDER BY rank DESC
LIMIT 20;
```

---

## Database Performance Tuning

### PostgreSQL Configuration

```sql
-- Increase shared buffers for large datasets
ALTER SYSTEM SET shared_buffers = '4GB';

-- Increase work memory for sorting
ALTER SYSTEM SET work_mem = '256MB';

-- Enable parallel query execution
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;

-- Analyze tables regularly
ANALYZE emails;
ANALYZE attachments;
```

### Partitioning Strategy

For very large email archives (millions of emails):

```sql
-- Partition emails by year
CREATE TABLE emails (
    -- ... columns ...
) PARTITION BY RANGE (date);

CREATE TABLE emails_2024 PARTITION OF emails
    FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

CREATE TABLE emails_2023 PARTITION OF emails
    FOR VALUES FROM ('2023-01-01') TO ('2024-01-01');
```

---

## Backup Strategy

### PostgreSQL

```bash
# Daily backup
pg_dump -Fc emailrag > backup_$(date +%Y%m%d).dump

# Point-in-time recovery
# Enable WAL archiving in postgresql.conf
wal_level = replica
archive_mode = on
archive_command = 'cp %p /backup/wal/%f'
```

### ChromaDB

```bash
# Backup ChromaDB data directory
tar -czf chromadb_backup_$(date +%Y%m%d).tar.gz /path/to/chromadb/data
```

---

## Migration Scripts

### Initial Setup

```sql
-- backend/migrations/001_initial.sql
BEGIN;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Create tables
-- (Full schema from above)

COMMIT;
```

### Adding Forensic Features

```sql
-- backend/migrations/002_forensic.sql
BEGIN;

ALTER TABLE emails ADD COLUMN spf_result TEXT;
ALTER TABLE emails ADD COLUMN dkim_result TEXT;
ALTER TABLE emails ADD COLUMN originating_ip INET;

CREATE TABLE evidence (...);

COMMIT;
```
