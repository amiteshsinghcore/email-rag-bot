"""
FastAPI Application Entry Point

Main application setup with middleware, routers, and lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1.router import api_router
from app.api.v1.endpoints.ws import router as ws_router
from app.config import settings
from app.core import close_cache, close_websocket, init_cache, init_websocket
from app.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info("Starting up Email RAG API...")

    await init_db()
    await init_cache()
    await init_websocket()

    logger.info("Email RAG API started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Email RAG API...")

    await close_websocket()
    await close_cache()
    await close_db()

    logger.info("Email RAG API shutdown complete")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="AI-powered email analysis system for PST files using RAG technology",
        version="1.0.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle uncaught exceptions."""
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """Health check endpoint for monitoring."""
        return {
            "status": "healthy",
            "app": settings.app_name,
            "version": "1.0.0",
        }

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    # Include WebSocket router (under /api/v1 prefix for consistency)
    app.include_router(ws_router, prefix="/api/v1")

    return app


# Create the application instance
app = create_application()
