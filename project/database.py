"""
companion/project/database.py

DB setup with connection pooling for production
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool

from project.config import settings

# Create engine with connection pooling
if settings.FASTAPI_CONFIG == "testing":
    # Use NullPool for testing (SQLite)
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=settings.DATABASE_CONNECT_DICT,
        poolclass=NullPool,
    )
else:
    # Use connection pooling for development/production
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=settings.DATABASE_POOL_PRE_PING,
        connect_args=settings.DATABASE_CONNECT_DICT,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


db_context = contextmanager(get_db_session)
