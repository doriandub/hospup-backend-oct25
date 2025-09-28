"""
Cache Service Interface

Defines the contract for caching operations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List
from datetime import timedelta


class ICacheService(ABC):
    """Cache service interface for high-performance data caching"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        expire_seconds: Optional[int] = None
    ) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            expire_seconds: Expiration time in seconds

        Returns:
            True if set successfully
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key

        Returns:
            True if key exists
        """
        pass

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment numeric value in cache

        Args:
            key: Cache key
            amount: Amount to increment by

        Returns:
            New value after increment
        """
        pass

    @abstractmethod
    async def get_multi(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache

        Args:
            keys: List of cache keys

        Returns:
            Dict mapping keys to values (missing keys omitted)
        """
        pass

    @abstractmethod
    async def set_multi(
        self,
        items: Dict[str, Any],
        expire_seconds: Optional[int] = None
    ) -> bool:
        """
        Set multiple values in cache

        Args:
            items: Dict mapping keys to values
            expire_seconds: Expiration time in seconds

        Returns:
            True if all items set successfully
        """
        pass

    @abstractmethod
    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern

        Args:
            pattern: Pattern to match (e.g., "user:*", "videos:123:*")

        Returns:
            Number of keys deleted
        """
        pass

    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get time-to-live for key

        Args:
            key: Cache key

        Returns:
            TTL in seconds, None if key doesn't exist or has no expiry
        """
        pass

    # Convenience methods for common patterns
    async def cache_user_data(
        self,
        user_id: int,
        data: Any,
        expire_minutes: int = 15
    ) -> bool:
        """Cache user-specific data with standard naming"""
        key = f"user:{user_id}:data"
        return await self.set(key, data, expire_minutes * 60)

    async def cache_property_data(
        self,
        property_id: str,
        data: Any,
        expire_minutes: int = 5
    ) -> bool:
        """Cache property-specific data with standard naming"""
        key = f"property:{property_id}:data"
        return await self.set(key, data, expire_minutes * 60)

    async def cache_video_data(
        self,
        video_id: str,
        data: Any,
        expire_minutes: int = 5
    ) -> bool:
        """Cache video-specific data with standard naming"""
        key = f"video:{video_id}:data"
        return await self.set(key, data, expire_minutes * 60)

    async def invalidate_user_cache(self, user_id: int) -> int:
        """Invalidate all cache entries for a user"""
        return await self.flush_pattern(f"user:{user_id}:*")

    async def invalidate_property_cache(self, property_id: str) -> int:
        """Invalidate all cache entries for a property"""
        return await self.flush_pattern(f"property:{property_id}:*")