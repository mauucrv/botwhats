"""
Redis cache service for caching salon data.
"""

import json
import structlog
from typing import Any, List, Optional

import redis.asyncio as redis

from app.config import settings

logger = structlog.get_logger(__name__)


class RedisCache:
    """Service for caching data in Redis."""

    # Cache keys
    SERVICES_KEY = "salon:services"
    STYLISTS_KEY = "salon:stylists"
    INFO_KEY = "salon:info"
    KEYWORDS_KEY = "salon:keywords_humano"

    def __init__(self):
        """Initialize the Redis cache."""
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        """Get or create the Redis client."""
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis client initialized")
        return self._client

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Redis connection closed")

    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            client = await self.get_client()
            await client.ping()
            return True
        except Exception as e:
            logger.error("Redis ping failed", error=str(e))
            return False

    # ============================================================
    # Generic cache operations
    # ============================================================

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        try:
            client = await self.get_client()
            value = await client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error("Error getting from cache", key=key, error=str(e))
            return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> bool:
        """Set a value in cache."""
        try:
            client = await self.get_client()
            serialized = json.dumps(value, default=str)
            if ttl:
                await client.setex(key, ttl, serialized)
            else:
                await client.set(key, serialized)
            return True
        except Exception as e:
            logger.error("Error setting cache", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        try:
            client = await self.get_client()
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error deleting from cache", key=key, error=str(e))
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists in cache."""
        try:
            client = await self.get_client()
            return await client.exists(key) > 0
        except Exception as e:
            logger.error("Error checking cache existence", key=key, error=str(e))
            return False

    # ============================================================
    # Services cache
    # ============================================================

    async def get_services(self) -> Optional[List[dict]]:
        """Get cached services."""
        return await self.get(self.SERVICES_KEY)

    async def set_services(self, services: List[dict]) -> bool:
        """Cache services."""
        return await self.set(
            self.SERVICES_KEY, services, settings.cache_ttl_services
        )

    async def invalidate_services(self) -> bool:
        """Invalidate services cache."""
        return await self.delete(self.SERVICES_KEY)

    # ============================================================
    # Stylists cache
    # ============================================================

    async def get_stylists(self) -> Optional[List[dict]]:
        """Get cached stylists."""
        return await self.get(self.STYLISTS_KEY)

    async def set_stylists(self, stylists: List[dict]) -> bool:
        """Cache stylists."""
        return await self.set(
            self.STYLISTS_KEY, stylists, settings.cache_ttl_stylists
        )

    async def invalidate_stylists(self) -> bool:
        """Invalidate stylists cache."""
        return await self.delete(self.STYLISTS_KEY)

    # ============================================================
    # Salon info cache
    # ============================================================

    async def get_info(self) -> Optional[dict]:
        """Get cached salon info."""
        return await self.get(self.INFO_KEY)

    async def set_info(self, info: dict) -> bool:
        """Cache salon info."""
        return await self.set(self.INFO_KEY, info, settings.cache_ttl_info)

    async def invalidate_info(self) -> bool:
        """Invalidate salon info cache."""
        return await self.delete(self.INFO_KEY)

    # ============================================================
    # Keywords cache
    # ============================================================

    async def get_keywords(self) -> Optional[List[str]]:
        """Get cached human keywords."""
        return await self.get(self.KEYWORDS_KEY)

    async def set_keywords(self, keywords: List[str]) -> bool:
        """Cache human keywords."""
        return await self.set(self.KEYWORDS_KEY, keywords, settings.cache_ttl_info)

    async def invalidate_keywords(self) -> bool:
        """Invalidate keywords cache."""
        return await self.delete(self.KEYWORDS_KEY)

    # ============================================================
    # Rate limiting
    # ============================================================

    async def check_rate_limit(
        self, phone_number: str, max_messages: int, window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if a phone number has exceeded the rate limit.

        Args:
            phone_number: The phone number to check
            max_messages: Maximum messages allowed in the window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, current_count)
        """
        try:
            client = await self.get_client()
            key = f"rate_limit:{phone_number}"

            # Get current count
            count = await client.get(key)
            current_count = int(count) if count else 0

            if current_count >= max_messages:
                logger.warning(
                    "Rate limit exceeded",
                    phone=phone_number[-4:],
                    count=current_count,
                )
                return False, current_count

            # Increment count
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            await pipe.execute()

            return True, current_count + 1

        except Exception as e:
            logger.error("Error checking rate limit", error=str(e))
            # Allow on error to avoid blocking users
            return True, 0

    async def get_rate_limit_remaining(
        self, phone_number: str, max_messages: int
    ) -> int:
        """
        Get remaining messages for a phone number.

        Args:
            phone_number: The phone number to check
            max_messages: Maximum messages allowed

        Returns:
            Number of remaining messages
        """
        try:
            client = await self.get_client()
            key = f"rate_limit:{phone_number}"
            count = await client.get(key)
            current_count = int(count) if count else 0
            return max(0, max_messages - current_count)
        except Exception as e:
            logger.error("Error getting rate limit remaining", error=str(e))
            return max_messages

    # ============================================================
    # Message grouping
    # ============================================================

    async def add_pending_message(
        self, conversation_id: int, message: dict, ttl: int = 60
    ) -> List[dict]:
        """
        Add a message to the pending messages list for a conversation.

        Args:
            conversation_id: The conversation ID
            message: The message to add
            ttl: Time to live in seconds

        Returns:
            List of all pending messages
        """
        try:
            client = await self.get_client()
            key = f"pending_messages:{conversation_id}"

            # Get existing messages
            existing = await client.get(key)
            messages = json.loads(existing) if existing else []

            # Add new message
            messages.append(message)

            # Save with TTL
            await client.setex(key, ttl, json.dumps(messages, default=str))

            return messages

        except Exception as e:
            logger.error("Error adding pending message", error=str(e))
            return [message]

    async def get_pending_messages(self, conversation_id: int) -> List[dict]:
        """
        Get pending messages for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            List of pending messages
        """
        try:
            client = await self.get_client()
            key = f"pending_messages:{conversation_id}"
            value = await client.get(key)
            return json.loads(value) if value else []
        except Exception as e:
            logger.error("Error getting pending messages", error=str(e))
            return []

    async def clear_pending_messages(self, conversation_id: int) -> bool:
        """
        Clear pending messages for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if successful
        """
        try:
            client = await self.get_client()
            key = f"pending_messages:{conversation_id}"
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error clearing pending messages", error=str(e))
            return False

    async def set_processing_lock(
        self, conversation_id: int, ttl: int = 30
    ) -> bool:
        """
        Set a processing lock for a conversation.

        Args:
            conversation_id: The conversation ID
            ttl: Lock timeout in seconds

        Returns:
            True if lock was acquired, False if already locked
        """
        try:
            client = await self.get_client()
            key = f"processing_lock:{conversation_id}"
            # Use SET NX (only set if not exists)
            result = await client.set(key, "1", ex=ttl, nx=True)
            return result is True
        except Exception as e:
            logger.error("Error setting processing lock", error=str(e))
            return False

    async def release_processing_lock(self, conversation_id: int) -> bool:
        """
        Release a processing lock for a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if successful
        """
        try:
            client = await self.get_client()
            key = f"processing_lock:{conversation_id}"
            await client.delete(key)
            return True
        except Exception as e:
            logger.error("Error releasing processing lock", error=str(e))
            return False

    # ============================================================
    # Conversation context
    # ============================================================

    async def get_conversation_context(
        self, conversation_id: int
    ) -> Optional[List[dict]]:
        """Get cached conversation context."""
        key = f"conversation_context:{conversation_id}"
        return await self.get(key)

    async def set_conversation_context(
        self, conversation_id: int, context: List[dict], ttl: int = 3600
    ) -> bool:
        """Cache conversation context."""
        key = f"conversation_context:{conversation_id}"
        return await self.set(key, context, ttl)

    async def clear_conversation_context(self, conversation_id: int) -> bool:
        """Clear cached conversation context."""
        key = f"conversation_context:{conversation_id}"
        return await self.delete(key)


# Singleton instance
redis_cache = RedisCache()
