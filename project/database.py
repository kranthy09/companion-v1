"""Optimized Database Setup with Advanced Pooling"""

from contextlib import contextmanager
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.pool import NullPool, QueuePool
from project.config import settings
import logging

logger = logging.getLogger(__name__)

# Production-grade pool configuration
POOL_CONFIG = {
    "pool_size": 20,  # Increased from 10
    "max_overflow": 40,  # Increased from 20
    "pool_timeout": 30,  # Wait time for connection
    "pool_recycle": 3600,  # Recycle connections every hour
    "pool_pre_ping": True,  # Verify connections before use
    "echo_pool": False,  # Set True for debugging
}

# Create engine with optimal settings
if settings.FASTAPI_CONFIG == "testing":
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=settings.DATABASE_CONNECT_DICT,
        poolclass=NullPool,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        poolclass=QueuePool,
        **POOL_CONFIG,
        connect_args={
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000"  # 30s query timeout
        }
    )


# Connection pool monitoring
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log new connections"""
    logger.debug("New database connection created")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Track connection checkouts"""
    pool = engine.pool
    logger.debug(
        f"Pool status: {pool.checkedout()}/{pool.size()} checked out, "
        f"{pool.overflow()} overflow"
    )


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Clean up on connection return"""
    # Reset session state
    dbapi_conn.rollback()


# Session configuration with optimizations
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,  # Manual control over flushes
    bind=engine,
    expire_on_commit=False  # Keep objects usable after commit
)

Base = declarative_base()


def get_db_session():
    """Dependency for FastAPI endpoints"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


db_context = contextmanager(get_db_session)


class DatabaseSessionManager:
    """Context manager for explicit session control"""

    def __init__(self):
        self.session: Optional[Session] = None

    def __enter__(self) -> Session:
        self.session = SessionLocal()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.session.rollback()
        else:
            self.session.commit()
        self.session.close()
        return False


def get_pool_stats() -> dict:
    """Get current pool statistics for monitoring"""
    pool_obj = engine.pool
    return {
        "size": pool_obj.size(),
        "checked_in": pool_obj.checkedin(),
        "checked_out": pool_obj.checkedout(),
        "overflow": pool_obj.overflow(),
        "total_connections": pool_obj.size() + pool_obj.overflow(),
        "available": pool_obj.size() - pool_obj.checkedout()
    }


def optimize_for_bulk_operations():
    """Context manager for bulk operations"""
    @contextmanager
    def _bulk_session():
        session = SessionLocal()
        try:
            # Disable autoflush for bulk operations
            session.autoflush = False
            # Use bulk operations
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _bulk_session()
