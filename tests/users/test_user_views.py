"""
tests/users/test_profile.py

Fixed test user profile endpoint
"""

import warnings

warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="passlib"
)


def test_get_user_profile_authenticated(client_no_middleware, db_session):
    """Test getting user profile with valid authentication"""
    # Register a user first
    user_data = {
        "email": "profiletest@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "1234567890",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    assert register_response.status_code == 200

    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test profile endpoint
    response = client_no_middleware.get("/users/profile", headers=headers)

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "id" in data
    assert "email" in data
    assert "full_name" in data
    assert "phone" in data
    assert "is_active" in data
    assert "is_verified" in data
    assert "created_at" in data
    assert "updated_at" in data

    # Verify data values
    assert data["email"] == user_data["email"]
    assert data["phone"] == user_data["phone"]
    assert data["is_active"] is True
    assert data["is_verified"] is False  # Default value

    # Verify ID is string representation of integer
    assert isinstance(data["id"], str)
    assert data["id"].isdigit()


def test_get_user_profile_unauthenticated(client_no_middleware):
    """
    Test getting user profile without authentication
    Unauthenticated requests: FastAPI's HTTPBearer()
    can return 403 when no token is provided
    """
    # Test with no Authorization header
    response = client_no_middleware.get("/users/profile")
    assert response.status_code == 403
    assert "detail" in response.json()

    # Test with empty headers explicitly
    response = client_no_middleware.get("/users/profile", headers={})
    assert response.status_code == 403
    assert "detail" in response.json()


def test_get_user_profile_invalid_token(client_no_middleware):
    """Test getting user profile with invalid token returns 401"""
    headers = {"Authorization": "Bearer invalid_token_here"}
    response = client_no_middleware.get("/users/profile", headers=headers)

    assert response.status_code == 401
    assert "detail" in response.json()


def test_debug_inactive_user(client_no_middleware, db_session):
    """Debug test to verify database session sharing"""
    from project.auth.models import User
    from project.auth.utils import get_password_hash, create_token_pair

    # Create inactive user
    hashed_password = get_password_hash("password123")
    user = User(
        email="debug_inactive@example.com",
        hashed_password=hashed_password,
        first_name="Debug",
        last_name="Inactive",
        is_active=False,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    print(f"Created user ID: {user.id}, Active: {user.is_active}")

    # Verify user exists in database
    found_user = (
        db_session.query(User)
        .filter(User.email == "debug_inactive@example.com")
        .first()
    )
    print(f"Found user in test session: {found_user is not None}")
    if found_user:
        print(f"Found user active status: {found_user.is_active}")

    # Create token and make request
    tokens = create_token_pair(user.email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client_no_middleware.get("/users/profile", headers=headers)

    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")

    # This should now return 400 instead of 401
    assert response.status_code == 400


def test_get_user_profile_inactive_user(client_no_middleware, db_session):
    """Test getting profile for inactive user returns 400"""
    from project.auth.models import User
    from project.auth.utils import get_password_hash, create_token_pair

    # Create inactive user directly in database
    hashed_password = get_password_hash("password123")
    user = User(
        email="inactive@example.com",
        hashed_password=hashed_password,
        first_name="Inactive",
        last_name="User",
        is_active=False,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create token for inactive user
    tokens = create_token_pair(user.email)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client_no_middleware.get("/users/profile", headers=headers)

    # Should return 400 for inactive user (not 403 or 401)
    assert response.status_code == 400
    assert "inactive" in response.json()["detail"].lower()


def test_get_user_profile_nonexistent_user_token(client_no_middleware):
    """Test getting profile with token for non-existent user"""
    from project.auth.utils import create_token_pair

    # Create token for email that doesn't exist in DB
    tokens = create_token_pair("nonexistent@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client_no_middleware.get("/users/profile", headers=headers)

    # Should return 401 when user not found
    assert response.status_code == 401
    assert "user not found" in response.json()["detail"].lower()


def test_get_user_profile_full_name_combinations(
    client_no_middleware, db_session
):
    """Test full_name property with different name combinations"""
    test_cases = [
        # (first_name, last_name, expected_full_name)
        ("John", "Doe", "John Doe"),
        ("Jane", None, "Jane"),
        (None, "Smith", "Smith"),
        (None, None, None),  # Will fall back to email
    ]

    for i, (first_name, last_name, expected_full_name) in enumerate(
        test_cases
    ):
        user_data = {
            "email": f"test{i}@example.com",
            "password": "password123",
        }

        if first_name:
            user_data["first_name"] = first_name
        if last_name:
            user_data["last_name"] = last_name

        register_response = client_no_middleware.post(
            "/auth/register", json=user_data
        )
        assert register_response.status_code == 200

        token = register_response.json()["token"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client_no_middleware.get("/users/profile", headers=headers)
        assert response.status_code == 200

        # For None names case, full_name should be email
        if expected_full_name is None:
            expected_full_name = user_data["email"]

        assert response.json()["full_name"] == expected_full_name
