#!/bin/bash
# ===========================================
# PST Email RAG Bot - Setup Script
# ===========================================

set -e

echo "=========================================="
echo "PST Email RAG Bot - Initial Setup"
echo "=========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env from .env.example...${NC}"
    cp .env.example .env
    echo -e "${GREEN}Created .env file. Please update with your settings.${NC}"
else
    echo -e "${GREEN}.env file already exists.${NC}"
fi

# Create necessary directories
echo -e "${YELLOW}Creating directories...${NC}"
mkdir -p uploads logs chroma_data

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. Please install Docker first.${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed. Please install Docker Compose.${NC}"
    exit 1
fi

echo -e "${GREEN}Docker is installed.${NC}"

# Start infrastructure services
echo -e "${YELLOW}Starting infrastructure services (PostgreSQL, Redis, RabbitMQ, ChromaDB)...${NC}"
docker-compose up -d postgres redis rabbitmq chromadb

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check if services are running
echo -e "${YELLOW}Checking service status...${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}=========================================="
echo "Setup Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Update .env with your API keys and settings"
echo "2. Run: cd backend && pip install -e .[dev]"
echo "3. Run: cd frontend && npm install"
echo "4. Run: alembic upgrade head (to create database tables)"
echo "5. Start backend: uvicorn app.main:app --reload"
echo "6. Start frontend: npm run dev"
echo ""
echo "Or use Docker:"
echo "  docker-compose up --build"
echo ""
