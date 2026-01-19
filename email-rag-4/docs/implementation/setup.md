# Setup Guide

## Prerequisites

### System Requirements
- **OS**: Linux, macOS, or Windows with WSL2
- **RAM**: Minimum 8GB, recommended 16GB
- **Storage**: 50GB free space
- **Python**: 3.11 or higher
- **Node.js**: 18 or higher
- **Docker**: 20.10 or higher (optional)

### Required Software
- Git
- PostgreSQL 15+
- Redis 7+
- Python 3.11+
- Node.js 18+
- npm or yarn

## Installation Steps

### 1. Clone Repository

```bash
git clone https://github.com/your-org/pst-email-rag-bot.git
cd pst-email-rag-bot
```

### 2. Environment Setup

Create environment file:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/email_rag
POSTGRES_USER=email_rag_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=email_rag

# Redis
REDIS_URL=redis://localhost:6379/0

# API Keys
OPENAI_API_KEY=your_openai_api_key

# Security
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ORIGINS=http://localhost:3000
```

### 3. Backend Setup

#### Install Dependencies

```bash
cd backend
pip install -r requirements.txt
# or using poetry
poetry install
```

#### Database Setup

Install PostgreSQL and create database:

```bash
sudo -u postgres psql
CREATE DATABASE email_rag;
CREATE USER email_rag_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE email_rag TO email_rag_user;
\q
```

Enable pgvector extension:

```bash
sudo -u postgres psql -d email_rag
CREATE EXTENSION vector;
\q
```

#### Run Migrations

```bash
alembic upgrade head
```

#### Start Backend Server

```bash
# Development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 4. Frontend Setup

#### Install Dependencies

```bash
cd frontend
npm install
# or
yarn install
```

#### Start Development Server

```bash
npm run dev
# or
yarn dev
```

Frontend will be available at `http://localhost:3000`

### 5. Worker Setup

Start Celery worker for background tasks:

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

Start Celery beat for scheduled tasks:

```bash
celery -A app.workers.celery_app beat --loglevel=info
```

## Docker Setup (Alternative)

### Using Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Services Included
- Backend API (port 8000)
- Frontend (port 3000)
- PostgreSQL (port 5432)
- Redis (port 6379)
- Celery worker
- Nginx (port 80)

## Database Initialization

### Create Admin User

```bash
cd backend
python -m app.scripts.create_admin
```

### Load Sample Data (Optional)

```bash
python -m app.scripts.load_sample_data
```

## Configuration

### Backend Configuration

Edit `backend/app/config.py` for advanced settings:

- Database connection pooling
- CORS settings
- Rate limiting
- File upload limits
- Vector database configuration

### Frontend Configuration

Edit `frontend/src/config.ts`:

- API endpoint URLs
- WebSocket URLs
- UI preferences
- Feature flags

## Verification

### Check Backend

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### Check Frontend

Open browser to `http://localhost:3000`

### Run Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test
```

## Troubleshooting

### Database Connection Issues

- Verify PostgreSQL is running: `systemctl status postgresql`
- Check connection string in `.env`
- Ensure pgvector extension is installed

### Redis Connection Issues

- Verify Redis is running: `systemctl status redis`
- Check Redis URL in `.env`
- Test connection: `redis-cli ping`

### Port Conflicts

- Change ports in `.env` or `docker-compose.yml`
- Check for processes using ports: `lsof -i :8000`

### Permission Issues

- Ensure proper file permissions
- Check database user permissions
- Verify Redis access

## Next Steps

- Upload your first PST file via the web interface
- Configure RAG settings
- Set up user accounts
- Review API documentation at `http://localhost:8000/docs`
