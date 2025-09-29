"""
project/middleware/performance.py - Performance monitoring
"""

import time
import logging
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Slow query threshold (seconds)
SLOW_QUERY_THRESHOLD = 1.0
SLOW_ENDPOINT_THRESHOLD = 2.0


class PerformanceMiddleware:
    """Track endpoint response times"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                duration = time.time() - start_time

                # Log slow endpoints
                if duration > SLOW_ENDPOINT_THRESHOLD:
                    path = scope.get("path", "")
                    method = scope.get("method", "")

                    extra = {
                        "method": method,
                        "path": path,
                        "duration_seconds": round(duration, 3),
                        "type": "slow_endpoint",
                    }

                    if "state" in scope and hasattr(
                        scope["state"], "request_id"
                    ):
                        extra["request_id"] = scope["state"].request_id

                    logger.warning(
                        "Slow endpoint detected", extra={"extra": extra}
                    )

            await send(message)

        await self.app(scope, receive, send_wrapper)


# SQL query monitoring
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(
    conn, cursor, statement, parameters, context, executemany
):
    total = time.time() - conn.info["query_start_time"].pop(-1)

    if total > SLOW_QUERY_THRESHOLD:
        # Truncate long queries
        query_preview = (
            statement[:200] + "..." if len(statement) > 200 else statement
        )

        extra = {
            "duration_seconds": round(total, 3),
            "query": query_preview,
            "type": "slow_query",
        }

        logger.warning("Slow query detected", extra={"extra": extra})


def get_db_pool_stats():
    """Get database connection pool statistics"""
    from project.database import engine

    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total": pool.size() + pool.overflow(),
    }
