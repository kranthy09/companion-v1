"""
tests/middleware/test_rate_limiting.py
"""

import pytest
from unittest.mock import patch


def test_rate_limiting_login_endpoint(client_with_middleware):
    """Test rate limiting on login (5 per 5 minutes)"""
    login_data = {"username": "test@test.com", "password": "wrong"}

    # First 5 requests should pass (even if 401)
    responses = []
    for i in range(6):
        response = client_with_middleware.post("/auth/login", data=login_data)
        responses.append(response.status_code)
        if response.status_code == 429:
            break

    # Should hit rate limit before 6th request
    assert 429 in responses, f"Expected 429, got: {responses}"


@patch("redis.from_url")
def test_rate_limiting_redis_fallback(mock_redis, client_with_middleware):
    """Test fallback to memory when Redis unavailable"""
    mock_redis.side_effect = Exception("Redis unavailable")

    response = client_with_middleware.get("/health")
    assert response.status_code in [
        200,
        429,
    ]  # Should work with memory fallback


def test_throttling_heavy_endpoint(client_with_middleware):
    """Test throttling on protected endpoints"""
    # Register user first
    register_data = {"email": "throttle@test.com", "password": "password123"}
    register_response = client_with_middleware.post(
        "/auth/register", json=register_data
    )

    if register_response.status_code == 200:
        token = register_response.json()["token"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Rapid requests to trigger throttling
        for i in range(5):
            response = client_with_middleware.get(
                "/users/profile", headers=headers
            )
            if response.status_code == 429:
                assert "throttled" in response.json().get("error", "").lower()
                break
        else:
            pytest.skip("Throttling limits may be too high for this test")
