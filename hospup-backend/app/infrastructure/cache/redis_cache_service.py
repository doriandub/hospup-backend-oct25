"""
Redis Cache Service Implementation

High-performance caching using Redis with connection pooling and retry logic.
"""

import json
import redis.asyncio as redis
import structlog
from typing import Any, Dict, List, Optional
from datetime import timedelta

from ...application.interfaces.cache_service import ICacheService
from ...domain.exceptions import ExternalServiceError

logger = structlog.get_logger(__name__)


class RedisCacheService(ICacheService):
    """
    Redis-based cache service implementation

    Features:
    - Connection pooling
    - Automatic serialization/deserialization
    - Circuit breaker pattern
    - Comprehensive error handling
    - Performance monitoring
    """

    def __init__(
        self,
        redis_url: str,
        max_connections: int = 20,
        socket_timeout: float = 5.0,
        socket_connect_timeout: float = 5.0,
        retry_on_timeout: bool = True,
        health_check_interval: int = 30
    ):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.socket_timeout = socket_timeout
        self.socket_connect_timeout = socket_connect_timeout
        self.retry_on_timeout = retry_on_timeout

        # Connection pool
        self._pool = None
        self._redis = None

        # Circuit breaker state
        self._is_healthy = True
        self._failure_count = 0
        self._max_failures = 3

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection with connection pooling"""
        if self._redis is None:
            if self._pool is None:
                self._pool = redis.ConnectionPool.from_url(
                    self.redis_url,
                    max_connections=self.max_connections,
                    socket_timeout=self.socket_timeout,
                    socket_connect_timeout=self.socket_connect_timeout,
                    retry_on_timeout=self.retry_on_timeout,
                    health_check_interval=30
                )
            self._redis = redis.Redis(connection_pool=self._pool)

        return self._redis

    async def _execute_with_circuit_breaker(self, operation, *args, **kwargs):
        """Execute Redis operation with circuit breaker pattern"""
        if not self._is_healthy:
            logger.warning("Cache circuit breaker is open, skipping operation")
            return None

        try:
            result = await operation(*args, **kwargs)
            # Reset failure count on success
            if self._failure_count > 0:
                self._failure_count = 0
                logger.info("Cache circuit breaker reset after success")
            return result

        except Exception as e:
            self._failure_count += 1
            logger.error(
                "Cache operation failed",
                error=str(e),
                failure_count=self._failure_count,
                operation=operation.__name__
            )

            # Open circuit breaker after max failures
            if self._failure_count >= self._max_failures:
                self._is_healthy = False
                logger.error("Cache circuit breaker opened due to failures")

            return None

    def _serialize_value(self, value: Any) -> str:
        """Serialize value for Redis storage"""
        try:
            if isinstance(value, (str, int, float, bool)):
                return json.dumps(value)
            return json.dumps(value, default=str)
        except Exception as e:
            logger.error("Failed to serialize cache value", error=str(e))
            raise ExternalServiceError(f"Cache serialization failed: {e}")

    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from Redis storage"""
        try:
            return json.loads(value)
        except Exception as e:
            logger.error("Failed to deserialize cache value", error=str(e))
            return value  # Return as string if JSON parsing fails

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        redis_client = await self._get_redis()

        async def _get_operation():
            value = await redis_client.get(key)
            if value is None:
                return None
            return self._deserialize_value(value.decode('utf-8'))

        result = await self._execute_with_circuit_breaker(_get_operation)

        if result is not None:
            logger.debug("Cache hit", key=key)
        else:
            logger.debug("Cache miss", key=key)

        return result

    async def set(
        self,
        key: str,
        value: Any,
        expire_seconds: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        redis_client = await self._get_redis()
        serialized_value = self._serialize_value(value)

        async def _set_operation():
            if expire_seconds:
                return await redis_client.setex(key, expire_seconds, serialized_value)
            else:
                return await redis_client.set(key, serialized_value)

        result = await self._execute_with_circuit_breaker(_set_operation)
        success = result is not None

        logger.debug(
            "Cache set",
            key=key,
            success=success,
            expire_seconds=expire_seconds
        )

        return success

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        redis_client = await self._get_redis()

        async def _delete_operation():
            return await redis_client.delete(key)

        result = await self._execute_with_circuit_breaker(_delete_operation)
        success = result == 1

        logger.debug("Cache delete", key=key, success=success)
        return success

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        redis_client = await self._get_redis()

        async def _exists_operation():
            return await redis_client.exists(key)

        result = await self._execute_with_circuit_breaker(_exists_operation)
        exists = result == 1

        logger.debug("Cache exists check", key=key, exists=exists)
        return exists

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment numeric value in cache"""
        redis_client = await self._get_redis()

        async def _incr_operation():
            if amount == 1:
                return await redis_client.incr(key)
            else:
                return await redis_client.incrby(key, amount)

        result = await self._execute_with_circuit_breaker(_incr_operation)

        if result is None:
            # Fallback: try to get current value and estimate
            current = await self.get(key)
            if isinstance(current, int):
                return current + amount
            return amount

        logger.debug("Cache increment", key=key, amount=amount, new_value=result)
        return result

    async def get_multi(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache"""
        if not keys:
            return {}

        redis_client = await self._get_redis()

        async def _mget_operation():
            values = await redis_client.mget(keys)
            result = {}
            for i, value in enumerate(values):
                if value is not None:
                    result[keys[i]] = self._deserialize_value(value.decode('utf-8'))
            return result

        result = await self._execute_with_circuit_breaker(_mget_operation)

        if result is None:
            return {}

        logger.debug("Cache multi-get", keys_requested=len(keys), keys_found=len(result))
        return result

    async def set_multi(
        self,
        items: Dict[str, Any],
        expire_seconds: Optional[int] = None
    ) -> bool:
        """Set multiple values in cache"""
        if not items:
            return True

        redis_client = await self._get_redis()

        async def _mset_operation():
            # Serialize all values
            serialized_items = {
                key: self._serialize_value(value)
                for key, value in items.items()
            }

            # Use pipeline for atomicity
            pipe = redis_client.pipeline()
            pipe.mset(serialized_items)

            if expire_seconds:
                for key in items.keys():
                    pipe.expire(key, expire_seconds)

            results = await pipe.execute()
            return all(results)

        result = await self._execute_with_circuit_breaker(_mset_operation)
        success = result is not None

        logger.debug(
            "Cache multi-set",
            items_count=len(items),
            success=success,
            expire_seconds=expire_seconds
        )

        return success

    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        redis_client = await self._get_redis()

        async def _flush_pattern_operation():
            # Get all keys matching pattern
            keys = await redis_client.keys(pattern)
            if not keys:
                return 0

            # Delete all matching keys
            deleted = await redis_client.delete(*keys)
            return deleted

        result = await self._execute_with_circuit_breaker(_flush_pattern_operation)
        deleted_count = result if result is not None else 0

        logger.info(
            "Cache pattern flush",
            pattern=pattern,
            deleted_count=deleted_count
        )

        return deleted_count

    async def get_ttl(self, key: str) -> Optional[int]:
        """Get time-to-live for key"""
        redis_client = await self._get_redis()

        async def _ttl_operation():
            ttl = await redis_client.ttl(key)
            return ttl if ttl > 0 else None

        result = await self._execute_with_circuit_breaker(_ttl_operation)
        logger.debug("Cache TTL check", key=key, ttl=result)
        return result

    async def health_check(self) -> bool:
        """Check cache service health"""
        try:
            redis_client = await self._get_redis()
            await redis_client.ping()
            self._is_healthy = True
            self._failure_count = 0
            return True
        except Exception as e:
            logger.error("Cache health check failed", error=str(e))
            self._is_healthy = False
            return False

    async def close(self) -> None:
        """Close Redis connections"""
        if self._redis:
            await self._redis.close()
        if self._pool:
            await self._pool.disconnect()