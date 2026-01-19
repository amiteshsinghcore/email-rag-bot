"""
Test Configuration and Fixtures

Shared fixtures for all tests including database setup,
test client, and mock services.

Note: Full database integration tests require PostgreSQL due to
PostgreSQL-specific types (ARRAY, TSVECTOR). Unit tests run without DB.
"""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import String, DateTime, Boolean
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.core.security import create_token_pair, get_password_hash
from app.db.models.user import UserRole

if TYPE_CHECKING:
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport


# ===========================================
# SQLite-compatible test models
# ===========================================

class TestBase(DeclarativeBase):
    """Base class for test models (SQLite compatible)."""
    pass


class TestUser(TestBase):
    """SQLite-compatible User model for testing."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# ===========================================
# Test Settings
# ===========================================

@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Create test settings with test database."""
    return Settings(
        app_env="testing",
        debug=True,
        secret_key="test-secret-key",
        jwt_secret_key="test-jwt-secret",
        postgres_host="localhost",
        postgres_port=5432,
        postgres_user="test",
        postgres_password="test",
        postgres_db="test_db",
        # Use SQLite for testing
        database_url="sqlite+aiosqlite:///:memory:",
        redis_host="localhost",
        redis_port=6379,
    )


# ===========================================
# Markers for database tests
# ===========================================

def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "requires_postgres: mark test as requiring PostgreSQL database"
    )


# ===========================================
# Database Fixtures
# ===========================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine(test_settings: Settings):
    """Create async database engine for tests using SQLite-compatible models."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    # Create tables using SQLite-compatible test models
    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)

    yield engine

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create database session for each test."""
    async_session_factory = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )

    async with async_session_factory() as session:
        yield session
        await session.rollback()


# ===========================================
# Test User Fixtures
# ===========================================

@pytest.fixture
def test_user_data() -> dict[str, Any]:
    """Generate test user data."""
    return {
        "email": "test@example.com",
        "username": "testuser",
        "password": "TestPass123!",
        "role": UserRole.INVESTIGATOR.value,
        "is_active": True,
        "is_verified": True,
    }


@pytest.fixture
async def test_user(db_session: AsyncSession, test_user_data: dict) -> TestUser:
    """Create a test user in the database."""
    user = TestUser(
        id=str(uuid4()),
        email=test_user_data["email"],
        username=test_user_data["username"],
        hashed_password=get_password_hash(test_user_data["password"]),
        role=test_user_data["role"],
        is_active=test_user_data["is_active"],
        is_verified=test_user_data["is_verified"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def test_admin_data() -> dict[str, Any]:
    """Generate test admin user data."""
    return {
        "email": "admin@example.com",
        "username": "adminuser",
        "password": "AdminPass123!",
        "role": UserRole.ADMIN.value,
        "is_active": True,
        "is_verified": True,
    }


@pytest.fixture
async def test_admin(db_session: AsyncSession, test_admin_data: dict) -> TestUser:
    """Create a test admin user in the database."""
    user = TestUser(
        id=str(uuid4()),
        email=test_admin_data["email"],
        username=test_admin_data["username"],
        hashed_password=get_password_hash(test_admin_data["password"]),
        role=test_admin_data["role"],
        is_active=test_admin_data["is_active"],
        is_verified=test_admin_data["is_verified"],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ===========================================
# Authentication Fixtures
# ===========================================

@pytest.fixture
def auth_token(test_user: TestUser) -> str:
    """Generate auth token for test user."""
    token_pair = create_token_pair(str(test_user.id), test_user.role)
    return token_pair.access_token


@pytest.fixture
def admin_token(test_admin: TestUser) -> str:
    """Generate auth token for admin user."""
    token_pair = create_token_pair(str(test_admin.id), test_admin.role)
    return token_pair.access_token


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Get authorization headers for test user."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Get authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


# ===========================================
# HTTP Client Fixtures (require PostgreSQL for full app)
# ===========================================

@pytest.fixture
async def app(db_session: AsyncSession, test_settings: Settings):
    """Create FastAPI app for testing.

    Note: This fixture requires PostgreSQL due to model constraints.
    Mark tests using this with @pytest.mark.requires_postgres
    """
    from fastapi import FastAPI
    from app.main import create_application

    application = create_application()

    # Override database dependency
    async def override_get_db():
        yield db_session

    from app.db.session import get_db
    application.dependency_overrides[get_db] = override_get_db

    return application


@pytest.fixture
async def client(app):
    """Create async HTTP client for testing."""
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture
async def authenticated_client(
    app,
    auth_headers: dict[str, str],
):
    """Create authenticated async HTTP client."""
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=auth_headers,
    ) as ac:
        yield ac


@pytest.fixture
async def admin_client(
    app,
    admin_headers: dict[str, str],
):
    """Create admin async HTTP client."""
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=admin_headers,
    ) as ac:
        yield ac


# ===========================================
# Mock Service Fixtures
# ===========================================

@pytest.fixture
def mock_redis() -> MagicMock:
    """Create mock Redis client."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=True)
    redis.exists = AsyncMock(return_value=False)
    redis.publish = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_chroma() -> MagicMock:
    """Create mock ChromaDB client."""
    chroma = MagicMock()
    collection = MagicMock()
    collection.add = MagicMock()
    collection.query = MagicMock(return_value={
        "ids": [["doc1", "doc2"]],
        "documents": [["Document 1 content", "Document 2 content"]],
        "metadatas": [[{"email_id": "1"}, {"email_id": "2"}]],
        "distances": [[0.1, 0.2]],
    })
    chroma.get_or_create_collection = MagicMock(return_value=collection)
    return chroma


@pytest.fixture
def mock_embedding_model() -> MagicMock:
    """Create mock embedding model."""
    model = MagicMock()
    # Return 384-dimensional embeddings (MiniLM)
    model.encode = MagicMock(return_value=[[0.1] * 384])
    return model


@pytest.fixture
def mock_llm() -> MagicMock:
    """Create mock LLM provider."""
    llm = MagicMock()
    llm.generate = AsyncMock(return_value="This is a test response from the LLM.")
    llm.generate_stream = AsyncMock()
    return llm


# ===========================================
# Sample Data Fixtures
# ===========================================

@pytest.fixture
def sample_email_data() -> dict[str, Any]:
    """Generate sample email data."""
    return {
        "id": str(uuid4()),
        "message_id": "<test123@example.com>",
        "thread_id": str(uuid4()),
        "sender_email": "sender@example.com",
        "sender_name": "Test Sender",
        "to_recipients": ["recipient@example.com"],
        "cc_recipients": [],
        "bcc_recipients": [],
        "subject": "Test Email Subject",
        "body_text": "This is the body of the test email.",
        "body_html": "<p>This is the body of the test email.</p>",
        "sent_date": datetime.now(timezone.utc),
        "received_date": datetime.now(timezone.utc),
        "importance": "normal",
        "is_read": False,
        "has_attachments": False,
        "folder_path": "Inbox",
        "pst_file_id": str(uuid4()),
    }


@pytest.fixture
def sample_pst_file_data() -> dict[str, Any]:
    """Generate sample PST file data."""
    return {
        "id": str(uuid4()),
        "filename": "test_emails.pst",
        "original_filename": "test_emails.pst",
        "file_size": 1024 * 1024 * 100,  # 100 MB
        "sha256_hash": "a" * 64,
        "status": "completed",
        "email_count": 1000,
        "user_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_search_query() -> dict[str, Any]:
    """Generate sample search query."""
    return {
        "query": "test email search",
        "filters": {
            "date_from": "2024-01-01",
            "date_to": "2024-12-31",
            "has_attachments": False,
        },
        "page": 1,
        "page_size": 20,
    }


@pytest.fixture
def sample_chat_request() -> dict[str, Any]:
    """Generate sample chat request."""
    return {
        "question": "What emails did John send last week?",
        "chat_history": [],
        "provider": "openai",
        "model": "gpt-4-turbo-preview",
        "stream": False,
        "top_k": 5,
        "temperature": 0.7,
    }
