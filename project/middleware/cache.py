"""Production-grade Redis caching middleware"""

import json
import hashlib
from typing import Optional, Callable
from functools import wraps
import redis.asyncio as aioredis
from fastapi.responses import JSONResponse
from project.config import settings
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """Async Redis cache with compression and TTL"""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.enabled = False

    async def init(self):
        """Initialize Redis connection"""
        try:
            self.redis = await aioredis.from_url(
                settings.CELERY_BROKER_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=50
            )
            await self.redis.ping()
            self.enabled = True
            logger.info("Redis cache initialized")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            self.enabled = False

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from args"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return f"cache:{hashlib.md5(key_data.encode()).hexdigest()}"

    async def get(self, key: str) -> Optional[dict]:
        """Get cached value"""
        if not self.enabled:
            return None

        try:
            data = await self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    async def set(
        self,
        key: str,
        value: dict,
        ttl: int = 300
    ) -> bool:
        """Set cache with TTL (seconds)"""
        if not self.enabled:
            return False

        try:
            await self.redis.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False

    async def delete(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        if not self.enabled:
            return 0

        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return 0

    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache for user"""
        await self.delete(f"cache:user:{user_id}:*")


# Global instance
cache = CacheManager()


def cached(
    ttl: int = 300,
    key_prefix: str = "",
    skip_if: Optional[Callable] = None
):
    """
    Decorator for caching function results.

    Usage:
        @cached(ttl=600, key_prefix="notes")
        async def get_note(note_id: int, user_id: UUID):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Skip caching condition
            if skip_if and skip_if(*args, **kwargs):
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = cache._make_key(
                key_prefix or func.__name__,
                *args,
                **kwargs
            )

            # Try cache
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_result

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            if result is not None:
                await cache.set(cache_key, result, ttl)
                logger.debug(f"Cache set: {cache_key}")

            return result

        return wrapper
    return decorator


class CacheMiddleware:
    """HTTP response caching middleware"""

    CACHEABLE_METHODS = {"GET", "HEAD"}
    CACHE_TTL = 60  # 1 minute default

    # Routes to cache
    CACHE_ROUTES = {
        "/notes": 60,
        "/notes/stats": 300,
        "/health": 10,
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request_path = scope.get("path", "")
        request_method = scope.get("method", "")

        # Check if route should be cached
        should_cache = False
        ttl = self.CACHE_TTL

        for route_prefix, route_ttl in self.CACHE_ROUTES.items():
            if request_path.startswith(route_prefix):
                should_cache = True
                ttl = route_ttl
                break

        # Only cache GET/HEAD requests
        if not (should_cache and request_method in self.CACHEABLE_METHODS):
            return await self.app(scope, receive, send)

        # Generate cache key
        cache_key = f"http:{request_method}:{request_path}"
        if scope.get("query_string"):
            cache_key += f"?{scope['query_string'].decode()}"

        # Check cache
        cached_response = await cache.get(cache_key)
        if cached_response:
            logger.debug(f"HTTP cache hit: {cache_key}")

            async def send_cached(message):
                if message["type"] == "http.response.start":
                    message["headers"].append((b"x-cache", b"hit"))
                await send(message)

            # Send cached response
            response = JSONResponse(cached_response["body"])
            await response(scope, receive, send_cached)
            return

        # Capture response
        response_body = []

        async def send_wrapper(message):
            if message["type"] == "http.response.body":
                response_body.append(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, send_wrapper)

        # Cache successful responses
        if response_body:
            try:
                body = b"".join(response_body)
                cache_data = {
                    "body": json.loads(body.decode()),
                    "status": 200
                }
                await cache.set(cache_key, cache_data, ttl)
                logger.debug(f"HTTP cache set: {cache_key}")
            except Exception as e:
                logger.error(f"Failed to cache response: {e}")
