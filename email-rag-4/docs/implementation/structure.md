# Project Structure

## Directory Layout

```
pst-email-rag-bot/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── config.py               # Configuration settings
│   │   ├── dependencies.py         # Dependency injection
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py     # Authentication endpoints
│   │   │   │   │   ├── emails.py   # Email operations
│   │   │   │   │   ├── search.py   # Search endpoints
│   │   │   │   │   ├── upload.py   # PST upload
│   │   │   │   │   └── users.py    # User management
│   │   │   │   └── router.py
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── security.py         # Security utilities
│   │   │   ├── logging.py          # Logging configuration
│   │   │   └── middleware.py       # Custom middleware
│   │   │
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Database base classes
│   │   │   ├── session.py          # Database sessions
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── email.py        # Email models
│   │   │       ├── user.py         # User models
│   │   │       └── attachment.py   # Attachment models
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── email.py            # Email schemas
│   │   │   ├── user.py             # User schemas
│   │   │   └── search.py           # Search schemas
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── email_service.py    # Email business logic
│   │   │   ├── search_service.py   # Search operations
│   │   │   ├── rag_service.py      # RAG engine
│   │   │   ├── pst_processor.py    # PST parsing
│   │   │   └── embedding_service.py # Embedding generation
│   │   │
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py       # Celery configuration
│   │   │   ├── email_tasks.py      # Email processing tasks
│   │   │   └── indexing_tasks.py   # Indexing tasks
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── helpers.py          # Utility functions
│   │       └── validators.py       # Validation functions
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py             # Pytest configuration
│   │   ├── test_api/
│   │   ├── test_services/
│   │   └── test_utils/
│   │
│   ├── alembic/                    # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/
│   ├── public/
│   │   └── index.html
│   │
│   ├── src/
│   │   ├── components/
│   │   │   ├── common/             # Reusable components
│   │   │   ├── email/              # Email components
│   │   │   ├── search/             # Search components
│   │   │   └── layout/             # Layout components
│   │   │
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Search.tsx
│   │   │   ├── EmailView.tsx
│   │   │   └── Settings.tsx
│   │   │
│   │   ├── services/
│   │   │   ├── api.ts              # API client
│   │   │   └── websocket.ts        # WebSocket client
│   │   │
│   │   ├── store/
│   │   │   ├── authStore.ts        # Auth state
│   │   │   └── emailStore.ts       # Email state
│   │   │
│   │   ├── hooks/
│   │   │   ├── useAuth.ts
│   │   │   └── useSearch.ts
│   │   │
│   │   ├── types/
│   │   │   └── index.ts            # TypeScript types
│   │   │
│   │   ├── utils/
│   │   │   └── helpers.ts
│   │   │
│   │   ├── App.tsx
│   │   └── main.tsx
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── docs/                           # Documentation (MkDocs)
│   ├── index.md
│   ├── requirements/
│   ├── architecture/
│   ├── implementation/
│   └── api/
│
├── scripts/
│   ├── setup.sh                    # Setup script
│   ├── migrate.sh                  # Migration script
│   └── backup.sh                   # Backup script
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
└── mkdocs.yml
```

## Key Directories

### Backend (`/backend`)
Contains the Python FastAPI application with all server-side logic.

### Frontend (`/frontend`)
React-based web application for the user interface.

### Docs (`/docs`)
MkDocs documentation source files.

### Scripts (`/scripts`)
Utility scripts for deployment and maintenance.

## Configuration Files

- **docker-compose.yml**: Multi-container Docker configuration
- **.env.example**: Environment variable template
- **mkdocs.yml**: Documentation configuration
- **pyproject.toml**: Python project configuration
- **package.json**: Node.js dependencies
