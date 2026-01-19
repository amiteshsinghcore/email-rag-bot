"""
Redis Cache Service

Provides caching utilities with TTL support and pub/sub for real-time events.
"""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, TypeVar

import redis.asyncio as redis
from loguru import logger

from app.config import settings

T = TypeVar("T")


class CacheService:
    """
    Redis-based caching service.

    Provides key-value caching, pub/sub, and rate limiting.
    """

    # Key prefixes for organization
    PREFIX_QUERY = "query"
    PREFIX_EMAIL = "email"
    PREFIX_SESSION = "session"
    PREFIX_TASK = "task"
    PREFIX_RATELIMIT = "ratelimit"
    PREFIX_LLM = "llm"

    def __init__(self) -> None:
        """Initialize Redis connection pool."""
        self._pool: redis.ConnectionPool | None = None
        self._client: redis.Redis | None = None
        self._pubsub: redis.client.PubSub | None = None

    @property
    def pool(self) -> redis.ConnectionPool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool.from_url(
                settings.redis_connection_url,
                max_connections=20,
                decode_responses=True,
            )
        return self._pool

    @property
    def client(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
        return self._client

    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            return await self.client.ping()
        except redis.RedisError as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connections."""
        if self._pubsub:
            await self._pubsub.close()
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()

    # ===========================================
    # Basic Cache Operations
    # ===========================================

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        try:
            return await self.client.get(key)
        except redis.RedisError as e:
            logger.error(f"Redis GET error for {key}: {e}")
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> bool:
        """
        Set a value in cache.

        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (optional)
        """
        try:
            if ttl:
                return await self.client.setex(key, ttl, value)
            return await self.client.set(key, value)
        except redis.RedisError as e:
            logger.error(f"Redis SET error for {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        try:
            await self.client.delete(key)
            return True
        except redis.RedisError as e:
            logger.error(f"Redis DELETE error for {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        try:
            return bool(await self.client.exists(key))
        except redis.RedisError as e:
            logger.error(f"Redis EXISTS error for {key}: {e}")
            return False

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration on a key."""
        try:
            return await self.client.expire(key, ttl)
        except redis.RedisError as e:
            logger.error(f"Redis EXPIRE error for {key}: {e}")
            return False

    # ===========================================
    # JSON Cache Operations
    # ===========================================

    async def get_json(self, key: str) -> Any | None:
        """Get and deserialize JSON from cache."""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for {key}: {e}")
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Serialize and set JSON in cache."""
        try:
            json_value = json.dumps(value, default=str)
            return await self.set(key, json_value, ttl)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON encode error for {key}: {e}")
            return False

    # ===========================================
    # Query Cache
    # ===========================================

    def query_key(self, query_hash: str) -> str:
        """Generate query cache key."""
        return f"{self.PREFIX_QUERY}:{query_hash}:results"

    async def get_query_results(self, query_hash: str) -> dict[str, Any] | None:
        """Get cached query results."""
        return await self.get_json(self.query_key(query_hash))

    async def set_query_results(
        self,
        query_hash: str,
        results: dict[str, Any],
    ) -> bool:
        """Cache query results."""
        return await self.set_json(
            self.query_key(query_hash),
            results,
            settings.cache_ttl_query,
        )

    async def invalidate_query_cache(self, pst_file_id: str | None = None) -> int:
        """
        Invalidate query cache.

        Args:
            pst_file_id: If provided, only invalidate queries for this PST file
        """
        pattern = f"{self.PREFIX_QUERY}:*"
        count = 0
        async for key in self.client.scan_iter(match=pattern):
            await self.delete(key)
            count += 1
        logger.info(f"Invalidated {count} query cache entries")
        return count

    # ===========================================
    # Email Metadata Cache
    # ===========================================

    def email_metadata_key(self, email_id: str) -> str:
        """Generate email metadata cache key."""
        return f"{self.PREFIX_EMAIL}:{email_id}:metadata"

    def email_body_key(self, email_id: str) -> str:
        """Generate email body cache key."""
        return f"{self.PREFIX_EMAIL}:{email_id}:body"

    async def get_email_metadata(self, email_id: str) -> dict[str, Any] | None:
        """Get cached email metadata."""
        return await self.get_json(self.email_metadata_key(email_id))

    async def set_email_metadata(
        self,
        email_id: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Cache email metadata."""
        return await self.set_json(
            self.email_metadata_key(email_id),
            metadata,
            settings.cache_ttl_email_metadata,
        )

    # ===========================================
    # Session Cache
    # ===========================================

    def session_key(self, token: str) -> str:
        """Generate session cache key."""
        return f"{self.PREFIX_SESSION}:{token}"

    async def get_session(self, token: str) -> dict[str, Any] | None:
        """Get cached session data."""
        return await self.get_json(self.session_key(token))

    async def set_session(
        self,
        token: str,
        session_data: dict[str, Any],
    ) -> bool:
        """Cache session data."""
        return await self.set_json(
            self.session_key(token),
            session_data,
            settings.cache_ttl_session,
        )

    async def delete_session(self, token: str) -> bool:
        """Delete session from cache."""
        return await self.delete(self.session_key(token))

    # ===========================================
    # Task Status Cache
    # ===========================================

    def task_status_key(self, task_id: str) -> str:
        """Generate task status cache key."""
        return f"{self.PREFIX_TASK}:{task_id}:status"

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get cached task status."""
        return await self.get_json(self.task_status_key(task_id))

    async def set_task_status(
        self,
        task_id: str,
        status: dict[str, Any],
    ) -> bool:
        """Cache task status (24 hour TTL)."""
        return await self.set_json(
            self.task_status_key(task_id),
            status,
            86400,  # 24 hours
        )

    # ===========================================
    # Rate Limiting
    # ===========================================

    def ratelimit_key(self, user_id: str, window: str) -> str:
        """Generate rate limit cache key."""
        return f"{self.PREFIX_RATELIMIT}:{user_id}:{window}"

    async def check_rate_limit(
        self,
        user_id: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Check and update rate limit.

        Returns:
            Tuple of (is_allowed, current_count, remaining)
        """
        window = str(int(import_time() / window_seconds))
        key = self.ratelimit_key(user_id, window)

        try:
            # Increment counter
            current = await self.client.incr(key)

            # Set expiry on first request in window
            if current == 1:
                await self.client.expire(key, window_seconds)

            is_allowed = current <= limit
            remaining = max(0, limit - current)

            return is_allowed, current, remaining

        except redis.RedisError as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open - allow request if Redis is down
            return True, 0, limit

    # ===========================================
    # LLM Response Cache
    # ===========================================

    def llm_response_key(self, prompt_hash: str) -> str:
        """Generate LLM response cache key."""
        return f"{self.PREFIX_LLM}:{prompt_hash}:response"

    async def get_llm_response(self, prompt_hash: str) -> str | None:
        """Get cached LLM response."""
        return await self.get(self.llm_response_key(prompt_hash))

    async def set_llm_response(
        self,
        prompt_hash: str,
        response: str,
    ) -> bool:
        """Cache LLM response."""
        return await self.set(
            self.llm_response_key(prompt_hash),
            response,
            settings.cache_ttl_llm_response,
        )

    # ===========================================
    # Pub/Sub for Real-time Updates
    # ===========================================

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """Publish a message to a channel."""
        try:
            return await self.client.publish(channel, json.dumps(message, default=str))
        except redis.RedisError as e:
            logger.error(f"Redis PUBLISH error: {e}")
            return 0

    @asynccontextmanager
    async def subscribe(
        self, *channels: str
    ) -> AsyncGenerator[redis.client.PubSub, None]:
        """
        Subscribe to channels for real-time updates.

        Usage:
            async with cache.subscribe("task:123", "notifications") as pubsub:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        data = json.loads(message["data"])
                        ...
        """
        pubsub = self.client.pubsub()
        try:
            await pubsub.subscribe(*channels)
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()

    async def publish_task_update(
        self,
        task_id: str,
        status: str,
        progress: float,
        message: str | None = None,
    ) -> None:
        """Publish a task progress update."""
        await self.publish(
            f"task:{task_id}",
            {
                "type": "task_update",
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "message": message,
            },
        )


def import_time() -> float:
    """Import time module and return current time."""
    import time
    return time.time()


# Global instance
cache = CacheService()


async def get_cache() -> CacheService:
    """Get the cache service instance."""
    return cache


async def init_cache() -> None:
    """Initialize cache connection."""
    if await cache.ping():
        logger.info("Redis cache connection established")
    else:
        logger.warning("Redis cache connection failed - caching disabled")


async def close_cache() -> None:
    """Close cache connection."""
    await cache.close()
    logger.info("Redis cache connection closed")
