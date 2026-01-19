"""
Database Session Management

Provides async SQLAlchemy session factory and dependency injection for FastAPI.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

# Create async engine for FastAPI (with connection pooling)
engine = create_async_engine(
    settings.async_database_url,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,  # Enable connection health checks
)

# Create session factory for FastAPI
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def _create_worker_engine():
    """Create a fresh engine for Celery workers (no pooling, fresh event loop)."""
    return create_async_engine(
        settings.async_database_url,
        echo=settings.debug,
        poolclass=NullPool,  # No pooling for workers - each task gets fresh connection
    )


def _create_worker_session_factory():
    """Create a fresh session factory for Celery workers."""
    worker_engine = _create_worker_engine()
    return async_sessionmaker(
        worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Usage in FastAPI:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions (for FastAPI).

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_worker_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for Celery worker database sessions.

    Creates a fresh engine and session for each call to avoid
    event loop issues in Celery workers.

    Usage in Celery tasks:
        async with get_worker_db_context() as db:
            result = await db.execute(...)
    """
    # Create fresh engine and session factory for this task
    worker_factory = _create_worker_session_factory()
    async with worker_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database connection pool."""
    # Test the connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Close database connection pool."""
    await engine.dispose()


# For testing - create engine without connection pooling
def create_test_engine(database_url: str) -> Any:
    """Create a test engine without connection pooling."""
    return create_async_engine(
        database_url,
        echo=True,
        poolclass=NullPool,
    )
