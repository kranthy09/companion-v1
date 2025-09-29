"""
project/monitoring.py - Monitoring endpoints
"""

from project.middleware.performance import get_db_pool_stats
from project.schemas.response import success_response
from . import monitoring_router


@monitoring_router.get("/db-pool")
def get_db_pool():
    """Database connection pool metrics"""
    stats = get_db_pool_stats()
    return success_response(data=stats, message="Database pool statistics")


@monitoring_router.get("/health/detailed")
def detailed_health():
    """Detailed health with performance metrics"""
    try:
        from project.database import engine

        # Test DB
        with engine.connect() as conn:
            conn.execute("SELECT 1")

        db_healthy = True
    except Exception:
        db_healthy = False

    try:
        import redis
        from project.config import settings

        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        redis_healthy = True
    except Exception:
        redis_healthy = False

    pool_stats = get_db_pool_stats()

    return success_response(
        data={
            "database": {"healthy": db_healthy, "pool": pool_stats},
            "redis": {"healthy": redis_healthy},
            "overall": db_healthy and redis_healthy,
        }
    )
