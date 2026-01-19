#!/bin/bash
# Database Backup Script for Email RAG Bot
set -e

# Configuration
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=7

# Load environment variables
if [ -f ".env.prod" ]; then
    export $(grep -v '^#' .env.prod | xargs)
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "Starting backup at $(date)"

# Backup PostgreSQL
echo "Backing up PostgreSQL database..."
docker-compose -f docker-compose.prod.yml exec -T postgres \
    pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_DIR/postgres_$DATE.sql.gz"

# Backup ChromaDB data
echo "Backing up ChromaDB data..."
docker cp email-rag-backend:/app/data/chroma "$BACKUP_DIR/chroma_$DATE" 2>/dev/null || echo "ChromaDB backup skipped (no data)"

# Backup uploads
echo "Backing up uploads..."
docker cp email-rag-backend:/app/uploads "$BACKUP_DIR/uploads_$DATE" 2>/dev/null || echo "Uploads backup skipped (no data)"

# Create combined archive
echo "Creating combined archive..."
tar -czf "$BACKUP_DIR/backup_$DATE.tar.gz" \
    "$BACKUP_DIR/postgres_$DATE.sql.gz" \
    "$BACKUP_DIR/chroma_$DATE" \
    "$BACKUP_DIR/uploads_$DATE" 2>/dev/null || true

# Cleanup individual files
rm -rf "$BACKUP_DIR/postgres_$DATE.sql.gz" "$BACKUP_DIR/chroma_$DATE" "$BACKUP_DIR/uploads_$DATE" 2>/dev/null || true

# Remove old backups
echo "Removing backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR/backup_$DATE.tar.gz"
echo "Backup finished at $(date)"
