# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PST Email RAG Bot is a full-stack application for extracting, indexing, and semantically searching emails from PST files using Retrieval-Augmented Generation (RAG). It combines:
- **Backend**: FastAPI microservices with Celery task queue
- **Frontend**: React/TypeScript web application
- **Infrastructure**: Docker containerized with PostgreSQL, Redis, RabbitMQ, ChromaDB

## Quick Start Commands

### Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs -f celery-worker

# Rebuild services (after dependency changes)
docker-compose build && docker-compose up -d

# Run backend migrations
docker-compose exec backend alembic upgrade head

# Access services
- Frontend: http://localhost:3000
- Backend API: http://localhost:8080
- RabbitMQ Management: http://localhost:15672 (guest/guest)
```

### Backend Testing & Linting
```bash
# Run tests
cd backend
pytest

# Run specific test
pytest tests/test_api/test_auth.py::test_login

# Lint & format
black app/
flake8 app/
mypy app/
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev      # Start dev server at http://localhost:5173
npm run build    # Production build
npm run lint     # ESLint
npm run type-check  # TypeScript check
```

## Architecture

### System Components

**Backend Services**:
- **FastAPI App**: REST API, WebSocket server, request routing
- **Celery Worker**: Async PST file processing, email extraction, embedding generation
- **Celery Beat**: Periodic scheduled tasks

**Data Layer**:
- **PostgreSQL**: Email metadata, users, processing tasks, LLM settings
- **ChromaDB**: Vector embeddings for RAG semantic search
- **Redis**: Caching, session storage, Celery result backend
- **RabbitMQ**: Message broker for Celery task queue

### Key Data Models

**Email** (`backend/app/db/models/email.py`):
- Core email entity with subject, sender, recipients, dates
- `body_text`, `body_html`: Full email content
- `sha256_hash`: Deduplication
- Foreign key to `ProcessingTask`

**ProcessingTask** (`backend/app/db/models/processing_task.py`):
- Tracks PST file processing status and progress
- States: PENDING → PARSING → EXTRACTING → EMBEDDING → COMPLETED/FAILED
- Stores metrics: `emails_total`, `emails_processed`, `emails_failed`

**Attachment** (`backend/app/db/models/attachment.py`):
- Email attachments with extracted text
- `is_extracted`: Whether text was successfully extracted
- `storage_path`: File system location

**User** (`backend/app/db/models/user.py`):
- Authentication and authorization
- Role-based access control

**LLMSettings** (`backend/app/db/models/llm_settings.py`):
- Database-driven LLM provider configuration
- Allows runtime switching between OpenAI, Anthropic, Google, xAI, Groq, Cerebras

### Processing Pipeline

**Email Extraction Flow**:
1. User uploads PST file → `POST /api/v1/upload`
2. Backend creates `ProcessingTask`, stores file
3. Celery task `process_pst_file()` triggered
4. PST parsing: `PSTProcessor` extracts emails
5. For each email:
   - Sanitize text (remove null bytes for PostgreSQL)
   - Save to database
   - Process attachments: extract text if possible (PDF, DOCX, etc.)
   - Save attachments to filesystem
6. Trigger embedding task: `embed_emails_for_task()`
7. Generate embeddings via sentence-transformers model
8. Index embeddings in ChromaDB

**Query/Chat Flow**:
1. User submits query → `POST /api/v1/rag/chat`
2. Query embedding generated
3. ChromaDB semantic search retrieves relevant emails
4. Metadata filtering (date range, sender filters, etc.)
5. Assemble context from top-k results
6. Call LLM with context + query
7. Stream response back via SSE or regular HTTP
8. Cache response for 10 minutes

### Critical Files & Their Purposes

**Backend**:
- `backend/app/main.py`: FastAPI app initialization, middleware, lifespan events
- `backend/app/config.py`: Environment variable parsing, settings validation
- `backend/app/api/v1/endpoints/upload.py`: PST file upload & processing task management
- `backend/app/api/v1/endpoints/rag.py`: Chat, embedding, RAG endpoints
- `backend/app/services/pst_processor.py`: libpff-based PST parsing
- `backend/app/services/embedding_service.py`: Sentence-transformers model loading & inference
- `backend/app/services/vector_store.py`: ChromaDB client & vector operations
- `backend/app/services/rag_service.py`: Query processing, context assembly, LLM integration
- `backend/app/services/attachment_processor.py`: Text extraction from PDF, DOCX, XLSX
- `backend/app/workers/email_tasks.py`: Core `process_pst_file()` & `cancel_processing()` tasks
- `backend/app/workers/indexing_tasks.py`: Embedding generation & ChromaDB indexing
- `backend/app/core/security.py`: JWT auth, password hashing (bcrypt)
- `backend/app/db/session.py`: Database session management & async context managers

**Frontend**:
- `frontend/src/App.tsx`: Main router configuration
- `frontend/src/pages/Upload.tsx`: PST file upload UI, processing status tracking
- `frontend/src/pages/Chat.tsx`: RAG chat interface with streaming responses
- `frontend/src/pages/Settings.tsx`: LLM provider configuration
- `frontend/src/services/api.ts`: API client (axios-based)
- `frontend/src/services/websocket.ts`: WebSocket connection for real-time updates
- `frontend/src/store/authStore.ts`: Authentication state (Zustand)

## Key Technical Decisions

### Celery Task Architecture
- Uses **RabbitMQ** as message broker (more reliable than Redis for this scale)
- Tasks routed to specific queues: `celery` (default), `email_processing` (PST tasks), `indexing` (embedding tasks)
- Worker configured to consume all queues: `-Q celery,email_processing,indexing`
- Each email in PST creates individual database transaction with error handling

### Text Sanitization
- PostgreSQL doesn't accept null bytes (`\x00`) in TEXT columns
- All text extracted from PDFs/documents is sanitized before DB insertion
- Removes control characters but preserves newlines, tabs
- See: `sanitize_text_for_db()` in `backend/app/services/attachment_processor.py`

### Async/Await Patterns
- Backend uses SQLAlchemy 2.0+ async ORM
- Celery tasks are **synchronous** but spawn new event loops for async operations
- `run_async()` helper in `email_tasks.py` manages event loop lifecycle
- Each task execution creates fresh event loop to prevent context contamination

### LLM Provider System
- Database-driven configuration allows runtime provider switching without restart
- Factory pattern in `backend/app/services/llm/factory.py` creates provider instances
- Supports: OpenAI, Anthropic, Google Gemini, xAI, Groq, Cerebras, custom endpoints
- Default provider configured via environment variable or database override

### Vector Database Choice
- **ChromaDB** chosen for its simplicity and local persistence
- Collections: `emails` (email body embeddings), `attachments` (extracted text embeddings)
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, fast)
- Batch embedding for performance: 256 emails per batch

## Common Development Scenarios

### Adding a New API Endpoint
1. Create handler in `backend/app/api/v1/endpoints/`
2. Add to router in `backend/app/api/v1/router.py`
3. Define Pydantic request/response schemas in `backend/app/schemas/`
4. Use dependency injection (`get_current_user`, `get_db`) from `backend/app/api/deps.py`

### Modifying Email Processing
- Core logic in `backend/app/workers/email_tasks.py:_process_pst_file_async()`
- Error handling at line ~362: `except Exception as e: emails_failed += 1; continue`
- Sanitization happens before database insertion
- Progress updates sent via Redis pub/sub to WebSocket clients

### Updating Database Schema
```bash
# Create migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec backend alembic upgrade head
```

### Debugging Celery Tasks
```bash
# Monitor task execution in real-time
docker-compose exec celery-worker celery -A app.workers.celery_app inspect active

# View task queue status
docker-compose exec celery-worker celery -A app.workers.celery_app inspect stats
```

### Known Issues & Workarounds

**Bcrypt Version Compatibility**:
- Pinned to `bcrypt==4.1.3` to avoid passlib version detection issues
- Newer versions (5.x) have strict 72-byte password enforcement

**Null Byte in PDF Text**:
- Some PDFs contain embedded null bytes that corrupt PostgreSQL storage
- Solution: Sanitize all extracted text before database operations

**Event Loop Contamination**:
- Original code reused event loops across tasks, causing greenlet errors
- Solution: Each Celery task creates fresh event loop with proper cleanup
- See `run_async()` function for cleanup pattern

## Environment Setup

Key environment variables (see `.env.example`):
- `SECRET_KEY`, `JWT_SECRET_KEY`: Security keys (randomize in production)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis cache connection
- `CELERY_BROKER_URL`: RabbitMQ broker URL
- `DEFAULT_LLM_PROVIDER`: Which LLM to use by default
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.: LLM API keys
- `CHROMA_HOST`, `CHROMA_PORT`: ChromaDB location
- `MAX_UPLOAD_SIZE_GB`: Maximum PST file size
- `VITE_API_URL`: Frontend API endpoint URL

## Performance Considerations

- **Email Extraction**: Bottleneck is libpff parsing (CPU-bound), not I/O
- **Embedding Generation**: Batched in groups of 256 for efficiency
- **Vector Search**: ChromaDB uses approximate nearest neighbor (fast, not exact)
- **Caching**: Redis caches frequent queries (10-minute TTL)
- **Database**: Connection pooling tuned to 10 connections with 20 overflow

## Git Workflow

This is a single-repository project (monorepo):
- `/backend`: Python FastAPI application
- `/frontend`: React/TypeScript application
- `/docs`: MkDocs documentation
- Changes to either backend or frontend may require rebuilds

Commit messages should reference which component changed (e.g., "backend: fix PST parsing for malformed emails").

## Testing Strategy

- Backend: pytest with async test fixtures in `backend/tests/`
- Frontend: Vitest with React Testing Library (minimal tests currently)
- Integration: Manual testing via Docker containers
- CI/CD: (not yet implemented, can be added to GitHub Actions)

## Deployment Notes

The application is designed for Docker deployment:
- All services containerized
- Data persistence via named volumes (postgres_data, chroma_data, etc.)
- Health checks configured for automatic restart
- Production-ready Dockerfiles with multi-stage builds

For Kubernetes: Docker images can be pushed to registry and orchestrated via Helm charts (not included).
