"""
companion/project/middleware/rate_limitter.py
"""

from fastapi import Request
from fastapi.responses import JSONResponse
import time
import redis
from typing import Dict
from project.config import settings


class RateLimiter:
    def __init__(self):
        try:
            self.redis = redis.from_url(settings.CELERY_BROKER_URL)
            self.storage = "redis"
        except Exception as e:
            print("Error: ", e)
            self.memory: Dict[str, list] = {}
            self.storage = "memory"

    def is_allowed(
        self, key: str, limit: int = 100, window: int = 3600
    ) -> bool:
        if self.storage == "redis":
            return self._redis_check(key, limit, window)
        return self._memory_check(key, limit, window)

    def _redis_check(self, key: str, limit: int, window: int) -> bool:
        try:
            pipe = self.redis.pipeline()
            now = time.time()
            pipe.zremrangebyscore(key, 0, now - window)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window)
            results = pipe.execute()
            return results[1] < limit
        except Exception as e:
            print("Error: ", e)
            return True  # Fail open

    def _memory_check(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        if key not in self.memory:
            self.memory[key] = []

        self.memory[key] = [
            req for req in self.memory[key] if now - req < window
        ]

        if len(self.memory[key]) >= limit:
            return False

        self.memory[key].append(now)
        return True


# Global instance
limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host

    # Define limits per endpoint
    limits = {
        "/auth/login": (5, 300),  # 5 per 5 minutes
        "/auth/register": (3, 3600),  # 3 per hour
        "/auth": (50, 3600),  # 50 per hour
    }

    path = request.url.path
    limit, window = limits.get("default", (1000, 3600))

    for pattern, (l, w) in limits.items():
        if path.startswith(pattern):
            limit, window = l, w
            break

    if not limiter.is_allowed(f"rate:{client_ip}:{path}", limit, window):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"},
            headers={"Retry-After": str(window)},
        )

    return await call_next(request)
