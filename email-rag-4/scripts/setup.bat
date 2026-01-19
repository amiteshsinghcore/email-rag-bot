@echo off
REM ===========================================
REM PST Email RAG Bot - Setup Script (Windows)
REM ===========================================

echo ==========================================
echo PST Email RAG Bot - Initial Setup
echo ==========================================

REM Check if .env exists
if not exist .env (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Created .env file. Please update with your settings.
) else (
    echo .env file already exists.
)

REM Create necessary directories
echo Creating directories...
if not exist uploads mkdir uploads
if not exist logs mkdir logs
if not exist chroma_data mkdir chroma_data

REM Check Docker
where docker >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

echo Docker is installed.

REM Start infrastructure services
echo Starting infrastructure services (PostgreSQL, Redis, RabbitMQ, ChromaDB)...
docker-compose up -d postgres redis rabbitmq chromadb

REM Wait for services
echo Waiting for services to start...
timeout /t 10 /nobreak >nul

REM Check service status
echo Checking service status...
docker-compose ps

echo.
echo ==========================================
echo Setup Complete!
echo ==========================================
echo.
echo Next steps:
echo 1. Update .env with your API keys and settings
echo 2. Run: cd backend ^&^& pip install -e .[dev]
echo 3. Run: cd frontend ^&^& npm install
echo 4. Run: alembic upgrade head (to create database tables)
echo 5. Start backend: uvicorn app.main:app --reload
echo 6. Start frontend: npm run dev
echo.
echo Or use Docker:
echo   docker-compose up --build
echo.
