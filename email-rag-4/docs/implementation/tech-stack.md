# Technology Stack

## Backend Technologies

### Core Framework
- **FastAPI**: Modern, fast web framework for building APIs
- **Python 3.11+**: Programming language
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: ORM for database operations

### Email Processing
- **pypff**: PST file parsing library
- **email**: Python standard library for email handling
- **libpff**: Microsoft PST file format parser

### AI/ML Stack
- **LangChain**: Framework for LLM applications
- **OpenAI API**: GPT models for generation
- **sentence-transformers**: Text embedding models
- **transformers**: Hugging Face library

## Database Technologies

### Primary Database
- **PostgreSQL 15+**: Relational database
- **pgvector**: Vector similarity search extension
- **pg_trgm**: Text search extension

### Vector Databases
- **ChromaDB**: Lightweight vector database
- **Pinecone**: Cloud-native vector database (alternative)
- **Weaviate**: Open-source vector database (alternative)

### Caching
- **Redis**: In-memory data structure store
- **redis-py**: Python Redis client

## Frontend Technologies

### Core Framework
- **React 18**: UI library
- **TypeScript**: Type-safe JavaScript
- **Vite**: Build tool and dev server

### UI Components
- **Material-UI**: React component library
- **TanStack Query**: Data fetching and caching
- **React Router**: Client-side routing

### State Management
- **Zustand**: Lightweight state management
- **React Context**: Built-in state sharing

## Infrastructure

### Containerization
- **Docker**: Container platform
- **Docker Compose**: Multi-container orchestration

### Web Server
- **Nginx**: Reverse proxy and load balancer
- **Uvicorn**: ASGI server for FastAPI

### Message Queue
- **RabbitMQ**: Message broker
- **Celery**: Distributed task queue
- **Redis**: Task result backend

## Development Tools

### Testing
- **pytest**: Python testing framework
- **pytest-asyncio**: Async test support
- **coverage.py**: Code coverage measurement
- **Jest**: JavaScript testing framework

### Code Quality
- **Black**: Python code formatter
- **isort**: Import sorting
- **Ruff**: Fast Python linter
- **ESLint**: JavaScript linter
- **Prettier**: Code formatter

### Documentation
- **MkDocs**: Documentation generator
- **Material for MkDocs**: Documentation theme
- **Swagger/OpenAPI**: API documentation

## Monitoring and Logging

### Application Monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Metrics visualization
- **Sentry**: Error tracking

### Logging
- **Loguru**: Python logging
- **ELK Stack**: Elasticsearch, Logstash, Kibana
- **Fluent Bit**: Log processor

## Security

### Authentication
- **JWT**: JSON Web Tokens
- **OAuth2**: Authorization framework
- **passlib**: Password hashing
- **python-jose**: JWT implementation

### Security Headers
- **CORS middleware**: Cross-origin resource sharing
- **helmet**: Security headers (frontend)

## Development Dependencies

### Version Control
- **Git**: Source control
- **pre-commit**: Git hooks framework

### Environment Management
- **Poetry**: Dependency management
- **pyenv**: Python version management
- **nvm**: Node version management

## Cloud Services (Optional)

### Object Storage
- **AWS S3**: File storage
- **MinIO**: Self-hosted object storage

### Cloud Platform
- **AWS**: Amazon Web Services
- **GCP**: Google Cloud Platform
- **Azure**: Microsoft Azure

## API Documentation
- **FastAPI**: Auto-generated OpenAPI docs
- **Redoc**: Alternative API documentation UI
- **Postman**: API testing and documentation
