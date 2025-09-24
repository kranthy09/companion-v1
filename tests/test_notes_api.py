"""
Example of how to use the Notes API with authentication
Run this after starting the application with docker-compose up
"""

import requests
import json

# Base URL - adjust port based on your docker-compose configuration
BASE_URL = "http://localhost:8010"

# Global token storage
ACCESS_TOKEN = None


def register_user():
    """Register a new user and get access token"""
    data = {
        "email": "testuser@example.com",
        "password": "testpass123",
    }

    response = requests.post(f"{BASE_URL}/auth/register", json=data)

    if response.status_code == 200:
        result = response.json()
        print("User registered successfully!")
        print(f"User ID: {result['user']['id']}")
        return result["token"]["access_token"]
    else:
        # Try login if registration fails (user might exist)
        return login_user()


def login_user():
    """Login existing user and get access token"""
    data = {"username": "testuser@example.com", "password": "testpass123"}

    response = requests.post(f"{BASE_URL}/auth/login", json=data)

    if response.status_code == 200:
        result = response.json()
        print("Login successful!")
        return result["access_token"]
    else:
        print("Login failed:", response.json())
        return None


def get_auth_headers():
    """Get authorization headers with JWT token"""
    global ACCESS_TOKEN
    if not ACCESS_TOKEN:
        ACCESS_TOKEN = register_user()

    return {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def test_create_note():
    """Create a new note"""
    data = {
        "title": "My First Note",
        "content": "This is the content of my first note.",
        "content_type": "text",
        "tags": ["test", "example", "first"],
    }

    response = requests.post(
        f"{BASE_URL}/notes/", headers=get_auth_headers(), json=data
    )

    print("Create Note Response:")
    print(json.dumps(response.json(), indent=2))

    if response.status_code == 201:
        return response.json()["data"]["id"]
    return None


def test_list_notes():
    """List all notes with pagination and filters"""
    params = {
        "page": 1,
        "page_size": 10,
        "sort_by": "created_at",
        "sort_order": "desc",
    }

    response = requests.get(
        f"{BASE_URL}/notes/", headers=get_auth_headers(), params=params
    )

    print("\nList Notes Response:")
    print(json.dumps(response.json(), indent=2))


def test_get_note(note_id):
    """Get a specific note by ID"""
    response = requests.get(
        f"{BASE_URL}/notes/{note_id}", headers=get_auth_headers()
    )

    print(f"\nGet Note {note_id} Response:")
    print(json.dumps(response.json(), indent=2))


def test_update_note(note_id):
    """Update an existing note"""
    data = {
        "title": "Updated Note Title",
        "content": "This is the updated content. Now with more information!",
        "tags": ["updated", "modified"],
    }

    response = requests.put(
        f"{BASE_URL}/notes/{note_id}", headers=get_auth_headers(), json=data
    )

    print(f"\nUpdate Note {note_id} Response:")
    print(json.dumps(response.json(), indent=2))


def test_search_notes():
    """Search notes with filters"""
    params = {
        "search": "test",
        "tags": ["example"],
        "content_type": "text",
        "page": 1,
        "page_size": 5,
    }

    response = requests.get(
        f"{BASE_URL}/notes/", headers=get_auth_headers(), params=params
    )

    print("\nSearch Notes Response:")
    print(json.dumps(response.json(), indent=2))


def test_get_stats():
    """Get user's notes statistics"""
    response = requests.get(
        f"{BASE_URL}/notes/stats/summary", headers=get_auth_headers()
    )

    print("\nNotes Statistics Response:")
    print(json.dumps(response.json(), indent=2))


def test_delete_note(note_id):
    """Delete a note"""
    response = requests.delete(
        f"{BASE_URL}/notes/{note_id}", headers=get_auth_headers()
    )

    print(f"\nDelete Note {note_id} Response:")
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    print("Testing Notes API with Authentication...")
    print("=" * 50)

    # Authenticate first
    ACCESS_TOKEN = register_user()

    if ACCESS_TOKEN:
        # Create a note
        note_id = test_create_note()

        if note_id:
            # List notes
            test_list_notes()

            # Get specific note
            test_get_note(note_id)

            # Update note
            test_update_note(note_id)

            # Search notes
            test_search_notes()

            # Get statistics
            test_get_stats()

            # Uncomment to delete the note
            # test_delete_note(note_id)
    else:
        print("Authentication failed. Cannot proceed with tests.")
