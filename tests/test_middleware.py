"""
Example of how to use the Middleware with APIs
Run this after starting the application with docker-compose up
"""

import requests
import concurrent.futures

BASE_URL = "http://localhost:8010"


def test_rate_limiting():
    """Test rate limiting on login endpoint (5 requests per 5 minutes)"""
    print("Testing Rate Limiting on /auth/login...")

    # Should allow first 5 requests
    for i in range(6):
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data={"username": "test@test.com", "password": "wrong"},
        )
        print(f"Request {i+1}: {response.status_code}")

        if response.status_code == 429:
            print(f"✅ Rate limited at request {i+1}")
            print(f"Headers: {dict(response.headers)}")
            return

    print("❌ Rate limiting not working")


def test_throttling():
    """Test throttling on heavy endpoint"""
    print("\nTesting Throttling on /users/transaction_celery...")

    # Create auth token first
    register_response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": "throttle@test.com", "password": "password123"},
    )

    if register_response.status_code == 200:
        token = register_response.json()["token"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Rapid requests to trigger throttling
        for i in range(5):
            response = requests.get(
                f"{BASE_URL}/users/transaction_celery/", headers=headers
            )
            print(f"Request {i+1}: {response.status_code}")

            if response.status_code == 429:
                print(f"✅ Throttled at request {i+1}")
                print(f"Response: {response.json()}")
                return

        print("❌ Throttling not working or limits too high")


def stress_test():
    """Concurrent requests to test both systems"""
    print("\nStress Testing with Concurrent Requests...")

    def make_request():
        try:
            response = requests.get(f"{BASE_URL}/")
            return response.status_code
        except Exception as e:
            print("Error: ", e)
            return 500

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(make_request) for _ in range(50)]
        results = [f.result() for f in futures]

    success_count = sum(1 for r in results if r == 200)
    blocked_count = sum(1 for r in results if r == 429)

    print(f"Successful: {success_count}")
    print(f"Rate limited: {blocked_count}")
    print(
        "✅ Middleware active"
        if blocked_count > 0
        else "❌ No rate limiting detected"
    )


def check_headers():
    """Check if rate limit headers are present"""
    print("\nChecking Response Headers...")

    response = requests.get(f"{BASE_URL}/")
    headers = response.headers

    rate_limit_headers = [
        h for h in headers if "rate" in h.lower() or "retry" in h.lower()
    ]
    if rate_limit_headers:
        print("✅ Rate limit headers found:")
        for header in rate_limit_headers:
            print(f"  {header}: {headers[header]}")
    else:
        print("❌ No rate limit headers found")


if __name__ == "__main__":
    test_rate_limiting()
    test_throttling()
    stress_test()
    check_headers()
