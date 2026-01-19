#!/bin/bash
# Production Deployment Script for Email RAG Bot
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Email RAG Bot - Production Deployment ${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo -e "${RED}Error: .env.prod file not found!${NC}"
    echo "Please create .env.prod with production environment variables."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env.prod | xargs)

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo -e "\n${YELLOW}Checking prerequisites...${NC}"

if ! command_exists docker; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    exit 1
fi

if ! command_exists docker-compose; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}All prerequisites met!${NC}"

# Create SSL directory if it doesn't exist
echo -e "\n${YELLOW}Setting up SSL certificates...${NC}"
mkdir -p nginx/ssl

if [ ! -f "nginx/ssl/fullchain.pem" ]; then
    echo -e "${YELLOW}Warning: SSL certificates not found in nginx/ssl/${NC}"
    echo "Please add your SSL certificates:"
    echo "  - nginx/ssl/fullchain.pem"
    echo "  - nginx/ssl/privkey.pem"
    echo ""
    read -p "Continue with self-signed certificates for testing? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Generating self-signed certificates..."
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout nginx/ssl/privkey.pem \
            -out nginx/ssl/fullchain.pem \
            -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        echo -e "${GREEN}Self-signed certificates generated!${NC}"
    else
        echo -e "${RED}Deployment cancelled.${NC}"
        exit 1
    fi
fi

# Build and deploy
echo -e "\n${YELLOW}Building production images...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache

echo -e "\n${YELLOW}Starting services...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be healthy
echo -e "\n${YELLOW}Waiting for services to be healthy...${NC}"
sleep 10

# Check health
echo -e "\n${YELLOW}Checking service health...${NC}"

check_health() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $service is healthy${NC}"
            return 0
        fi
        echo "Waiting for $service... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    echo -e "${RED}✗ $service failed to become healthy${NC}"
    return 1
}

check_health "Backend" "http://localhost:8000/health"
check_health "Frontend" "http://localhost:80/health"

# Run database migrations
echo -e "\n${YELLOW}Running database migrations...${NC}"
docker-compose -f docker-compose.prod.yml exec -T backend alembic upgrade head

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!                  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Access the application at: https://localhost"
echo ""
echo "Useful commands:"
echo "  docker-compose -f docker-compose.prod.yml logs -f    # View logs"
echo "  docker-compose -f docker-compose.prod.yml ps         # Check status"
echo "  docker-compose -f docker-compose.prod.yml down       # Stop services"
