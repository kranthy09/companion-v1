from fastapi import Request
from fastapi.responses import JSONResponse
import time
from typing import Dict


class TokenBucket:
    def __init__(self, capacity: int = 10, refill_rate: float = 1.0):
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.time()

    def consume(self) -> bool:
        now = time.time()
        elapsed = now - self.last_refill

        self.tokens = min(
            self.capacity, self.tokens + (elapsed * self.refill_rate)
        )
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class Throttler:
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}

    def get_bucket(
        self, key: str, capacity: int = 10, rate: float = 1.0
    ) -> TokenBucket:
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(capacity, rate)
        return self.buckets[key]


# Global instance
throttler = Throttler()


async def throttle_middleware(request: Request, call_next):
    client_ip = request.client.host
    path = request.url.path

    # Define throttling per endpoint
    configs = {
        "/users/transaction_celery": (3, 0.1),  # 3 capacity, 1 per 10 seconds
        "/users/subscribe": (5, 0.2),  # 5 capacity, 1 per 5 seconds
        "default": (50, 5.0),  # 50 capacity, 5 per second
    }

    capacity, rate = configs.get(path, configs["default"])
    bucket = throttler.get_bucket(
        f"throttle:{client_ip}:{path}", capacity, rate
    )

    if not bucket.consume():
        delay = 1.0 / rate if rate > 0 else 5.0
        return JSONResponse(
            status_code=429,
            content={"error": "Request throttled", "retry_after": delay},
            headers={"Retry-After": str(int(delay))},
        )

    return await call_next(request)
