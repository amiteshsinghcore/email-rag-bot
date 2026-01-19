"""
Application Configuration Module

Loads configuration from environment variables with sensible defaults.
Uses pydantic-settings for validation and type coercion.
"""

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ===========================================
    # Application Settings
    # ===========================================
    app_name: str = Field(default="PST Email RAG Bot")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    secret_key: str = Field(default="change-me-in-production")

    # API Settings
    api_v1_prefix: str = Field(default="/api/v1")
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    # ===========================================
    # Database Configuration
    # ===========================================
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="pstrag")
    postgres_password: str = Field(default="pstrag_password")
    postgres_db: str = Field(default="pstrag_db")
    database_url: str | None = Field(default=None)

    # Connection pool settings
    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    db_pool_timeout: int = Field(default=30)

    @property
    def async_database_url(self) -> str:
        """Get async database URL for SQLAlchemy."""
        if self.database_url:
            # Replace postgresql:// with postgresql+asyncpg://
            url = self.database_url
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        """Get sync database URL for Alembic."""
        if self.database_url:
            url = self.database_url
            if "+asyncpg" in url:
                return url.replace("+asyncpg", "", 1)
            return url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ===========================================
    # Redis Configuration
    # ===========================================
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)
    redis_password: str | None = Field(default=None)
    redis_db: int = Field(default=0)
    redis_url: str | None = Field(default=None)

    @property
    def redis_connection_url(self) -> str:
        """Get Redis connection URL."""
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ===========================================
    # RabbitMQ / Celery Configuration
    # ===========================================
    rabbitmq_host: str = Field(default="localhost")
    rabbitmq_port: int = Field(default=5672)
    rabbitmq_user: str = Field(default="pstrag")
    rabbitmq_password: str = Field(default="pstrag_password")
    rabbitmq_vhost: str = Field(default="/")
    celery_broker_url: str | None = Field(default=None)
    celery_result_backend: str | None = Field(default=None)

    @property
    def celery_broker(self) -> str:
        """Get Celery broker URL."""
        if self.celery_broker_url:
            return self.celery_broker_url
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/{self.rabbitmq_vhost}"
        )

    @property
    def celery_backend(self) -> str:
        """Get Celery result backend URL."""
        if self.celery_result_backend:
            return self.celery_result_backend
        # If redis_url is set, use it (change db to 1 for results)
        if self.redis_url:
            # Parse and modify the redis_url to use db 1 for celery results
            url = self.redis_url
            if url.endswith("/0"):
                url = url[:-2] + "/1"
            elif not url.split("/")[-1].isdigit():
                url = url.rstrip("/") + "/1"
            return url
        return f"redis://{self.redis_host}:{self.redis_port}/1"

    # ===========================================
    # ChromaDB Configuration
    # ===========================================
    chroma_host: str | None = Field(default=None)  # None = use persistent local storage
    chroma_port: int | None = Field(default=None)
    chroma_persist_directory: str = Field(default="/app/data/chroma")

    # ===========================================
    # LLM Provider Configuration
    # ===========================================
    # OpenAI
    openai_api_key: str | None = Field(default=None)
    openai_model: str = Field(default="gpt-4-turbo-preview")

    # Anthropic
    anthropic_api_key: str | None = Field(default=None)
    anthropic_model: str = Field(default="claude-3-sonnet-20240229")

    # Google
    google_api_key: str | None = Field(default=None)
    google_model: str = Field(default="gemini-pro")

    # xAI
    xai_api_key: str | None = Field(default=None)
    xai_model: str = Field(default="grok-beta")

    # Groq
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # Cerebras
    cerebras_api_key: str | None = Field(default=None)
    cerebras_model: str = Field(default="llama-3.3-70b")

    # Custom LLM
    custom_llm_base_url: str | None = Field(default=None)
    custom_llm_api_key: str | None = Field(default=None)
    custom_llm_model: str | None = Field(default=None)

    # Default provider
    default_llm_provider: str = Field(default="openai")

    # ===========================================
    # Embedding Configuration
    # ===========================================
    embedding_model: str = Field(default="all-MiniLM-L6-v2")
    embedding_dimension: int = Field(default=384)
    embedding_batch_size: int = Field(default=256)
    embedding_chunk_size: int = Field(default=512)
    embedding_chunk_overlap: int = Field(default=50)

    # ===========================================
    # File Upload Settings
    # ===========================================
    max_upload_size_gb: int = Field(default=50)
    upload_dir: str = Field(default="/app/uploads")
    allowed_extensions: str = Field(default=".pst")

    @property
    def max_upload_size_bytes(self) -> int:
        """Get max upload size in bytes."""
        return self.max_upload_size_gb * 1024 * 1024 * 1024

    @property
    def upload_directory(self) -> str:
        """Alias for upload_dir."""
        return self.upload_dir

    # ===========================================
    # JWT Authentication
    # ===========================================
    jwt_secret_key: str = Field(default="jwt-secret-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # ===========================================
    # Rate Limiting
    # ===========================================
    rate_limit_standard: int = Field(default=100)
    rate_limit_investigator: int = Field(default=500)
    rate_limit_admin: int = Field(default=1000)
    rate_limit_unauthenticated: int = Field(default=10)
    rate_limit_window_seconds: int = Field(default=60)

    # ===========================================
    # Logging
    # ===========================================
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_file: str = Field(default="./logs/app.log")

    # ===========================================
    # Performance Settings
    # ===========================================
    worker_pool_size: int = Field(default=4)

    # Cache TTLs (in seconds)
    cache_ttl_query: int = Field(default=300)  # 5 minutes
    cache_ttl_email_metadata: int = Field(default=3600)  # 1 hour
    cache_ttl_session: int = Field(default=1800)  # 30 minutes
    cache_ttl_llm_response: int = Field(default=600)  # 10 minutes
    cache_ttl_embeddings: int = Field(default=86400)  # 24 hours


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
