# ===========================================
# PST Email RAG Bot - Backend Dockerfile
# ===========================================
# Multi-stage build for optimized production image

# ----- Build Stage -----
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ----- Production Stage -----
FROM python:3.11-slim as production

WORKDIR /app

# Create non-root user for security with home directory for model cache
RUN groupadd -r pstrag && useradd -r -g pstrag -m -d /home/pstrag pstrag

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --timeout=600 --no-cache /wheels/*

# Copy application code
COPY --chown=pstrag:pstrag . .

# Create necessary directories
RUN mkdir -p /app/uploads /app/logs /app/chroma_data \
    && chown -R pstrag:pstrag /app

# Switch to non-root user
USER pstrag

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
