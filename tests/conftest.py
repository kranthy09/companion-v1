"""
tests/conftest.py

Complete test fixtures with proper DB session override
"""

import os
import pytest
from contextlib import asynccontextmanager
import warnings

warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="passlib"
)

# Set testing environment before imports
os.environ["FASTAPI_CONFIG"] = "testing"


@pytest.fixture(scope="session")
def engine():
    """Database engine for tests"""
    from project.database import engine as test_engine

    return test_engine


@pytest.fixture(scope="session")
def create_tables(engine):
    """Create all tables once per test session"""
    from project.database import Base

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(engine, create_tables):
    """Database session for individual tests"""
    from project.database import SessionLocal

    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app_no_middleware(db_session):
    """Minimal app without rate limiting middleware"""
    from fastapi import FastAPI
    from project import broadcast
    from fastapi.middleware.cors import CORSMiddleware
    from project.database import get_db_session

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await broadcast.connect()
        yield
        await broadcast.disconnect()

    app = FastAPI(title="Test API", lifespan=lifespan, debug=True)

    # CRITICAL: Override database dependency
    def get_test_db_session():
        return db_session

    app.dependency_overrides[get_db_session] = get_test_db_session

    # Add CORS only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize Celery
    from project.celery_utils import create_celery

    app.celery_app = create_celery()

    # Add routers
    from project.auth import auth_router
    from project.users import users_router
    from project.notes import notes_router
    from project.health import health_router
    from project.ws import ws_router

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    app.include_router(notes_router)
    app.include_router(ws_router)

    @app.get("/")
    def root():
        return {"message": "Test API"}

    return app


@pytest.fixture
def client_no_middleware(app_no_middleware):
    """Test client without middleware"""
    from fastapi.testclient import TestClient

    return TestClient(app_no_middleware)


@pytest.fixture
def app_with_middleware(db_session):
    """Full app with all middleware for middleware testing"""
    from project import create_app
    from project.database import get_db_session

    app = create_app()

    # Override database dependency for middleware tests too
    def get_test_db_session():
        return db_session

    app.dependency_overrides[get_db_session] = get_test_db_session

    return app


@pytest.fixture
def client_with_middleware(app_with_middleware):
    """Test client with middleware enabled"""
    from fastapi.testclient import TestClient

    return TestClient(app_with_middleware)
