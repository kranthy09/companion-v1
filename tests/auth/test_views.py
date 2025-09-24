"""
tests/auth/test_views.py

Fixed tests with proper dependency override
"""

from project.auth.models import User


# In conftest.py or test files
import warnings

warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="passlib"
)


def test_pytest_setup(client_no_middleware, db_session):
    """Test basic setup works"""
    # Override dependency

    # Test health endpoint
    response = client_no_middleware.get("/health")
    assert response.status_code == 200

    # Test database
    user = User(
        email="test@example.com",
        hashed_password="hashed_password_123",
        first_name="Test",
        last_name="User",
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"


def test_register_user(client_no_middleware, db_session):
    """Test user registration without rate limits"""

    user_data = {
        "email": "newuser@example.com",
        "password": "password123",
        "first_name": "New",
        "last_name": "User",
    }

    response = client_no_middleware.post("/auth/register", json=user_data)
    assert response.status_code == 200

    data = response.json()
    assert "user" in data
    assert "token" in data
    assert data["user"]["email"] == user_data["email"]


def test_login_user(client_no_middleware, db_session):
    """Test user login without rate limits"""
    # Register user first
    user_data = {
        "email": "logintest@example.com",
        "password": "password123",
    }
    client_no_middleware.post("/auth/register", json=user_data)

    # Test login
    login_data = {
        "username": "logintest@example.com",
        "password": "password123",
    }

    response = client_no_middleware.post("/auth/login", data=login_data)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "token_type" in data
