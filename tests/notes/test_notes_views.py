"""
tests/notes/test_notes_views.py

Test cases for Notes App views
"""

import warnings

warnings.filterwarnings(
    "ignore", category=DeprecationWarning, module="passlib"
)


def test_create_note_success(client_no_middleware, db_session):
    """Test creating a note with valid authentication"""
    # Register and login user
    user_data = {
        "email": "noteuser@example.com",
        "password": "password123",
        "first_name": "Note",
        "last_name": "User",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    assert register_response.status_code == 200

    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create note
    note_data = {
        "title": "Test Note",
        "content": "This is a test note content",
        "content_type": "text",
        "tags": ["test", "sample"],
    }

    response = client_no_middleware.post(
        "/notes/", json=note_data, headers=headers
    )
    assert response.status_code == 201

    data = response.json()
    assert data["success"] is True
    assert data["data"]["title"] == note_data["title"]
    assert data["data"]["content"] == note_data["content"]
    assert data["data"]["tags"] == note_data["tags"]
    assert data["message"] == "Note created successfully"


def test_create_note_unauthenticated(client_no_middleware):
    """Test creating note without authentication returns 403"""
    note_data = {
        "title": "Unauthorized Note",
        "content": "This should fail",
    }

    response = client_no_middleware.post("/notes/", json=note_data)
    assert response.status_code == 403


def test_list_notes_success(client_no_middleware, db_session):
    """Test listing notes with pagination"""
    # Register user and create notes
    user_data = {
        "email": "listuser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create multiple notes
    for i in range(3):
        note_data = {
            "title": f"Note {i+1}",
            "content": f"Content for note {i+1}",
            "tags": [f"tag{i}"],
        }
        client_no_middleware.post("/notes/", json=note_data, headers=headers)

    # List notes
    response = client_no_middleware.get("/notes/", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 3
    assert data["total_count"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 20


def test_list_notes_with_search(client_no_middleware, db_session):
    """Test listing notes with search functionality"""
    user_data = {
        "email": "searchuser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create notes with different content
    notes = [
        {"title": "Python Tutorial", "content": "Learn Python programming"},
        {"title": "JavaScript Guide", "content": "Web development with JS"},
        {"title": "Database Design", "content": "SQL and NoSQL concepts"},
    ]

    for note in notes:
        client_no_middleware.post("/notes/", json=note, headers=headers)

    # Search for Python
    response = client_no_middleware.get(
        "/notes/?search=Python", headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert "Python" in data["data"][0]["title"]


def test_list_notes_unauthenticated(client_no_middleware):
    """Test listing notes without authentication returns 403"""
    response = client_no_middleware.get("/notes/")
    assert response.status_code == 403


def test_get_note_success(client_no_middleware, db_session):
    """Test getting a specific note by ID"""
    # Setup user and create note
    user_data = {
        "email": "getuser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    note_data = {
        "title": "Specific Note",
        "content": "This note will be retrieved by ID",
    }

    create_response = client_no_middleware.post(
        "/notes/", json=note_data, headers=headers
    )
    note_id = create_response.json()["data"]["id"]

    # Get the note
    response = client_no_middleware.get(f"/notes/{note_id}", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] == note_id
    assert data["data"]["title"] == note_data["title"]
    assert data["message"] == "Note retrieved successfully"


def test_get_note_not_found(client_no_middleware, db_session):
    """Test getting non-existent note returns 404"""
    user_data = {
        "email": "notfounduser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Try to get non-existent note
    response = client_no_middleware.get("/notes/99999", headers=headers)
    assert response.status_code == 404
    assert "Note not found" in response.json()["detail"]


def test_get_note_unauthenticated(client_no_middleware):
    """Test getting note without authentication returns 403"""
    response = client_no_middleware.get("/notes/1")
    assert response.status_code == 403


def test_update_note_success(client_no_middleware, db_session):
    """Test updating an existing note"""
    # Setup user and create note
    user_data = {
        "email": "updateuser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    note_data = {
        "title": "Original Title",
        "content": "Original content",
        "tags": ["original"],
    }

    create_response = client_no_middleware.post(
        "/notes/", json=note_data, headers=headers
    )
    note_id = create_response.json()["data"]["id"]

    # Update the note
    update_data = {
        "title": "Updated Title",
        "content": "Updated content",
        "tags": ["updated", "modified"],
    }

    response = client_no_middleware.put(
        f"/notes/{note_id}", json=update_data, headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["data"]["title"] == update_data["title"]
    assert data["data"]["content"] == update_data["content"]
    assert data["data"]["tags"] == update_data["tags"]
    assert data["message"] == "Note updated successfully"


def test_update_note_not_found(client_no_middleware, db_session):
    """Test updating non-existent note returns 404"""
    user_data = {
        "email": "updatenotfound@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_data = {"title": "Updated Title"}

    response = client_no_middleware.put(
        "/notes/99999", json=update_data, headers=headers
    )
    assert response.status_code == 404
    assert "Note not found" in response.json()["detail"]


def test_update_note_unauthenticated(client_no_middleware):
    """Test updating note without authentication returns 403"""
    update_data = {"title": "Should Fail"}
    response = client_no_middleware.put("/notes/1", json=update_data)
    assert response.status_code == 403


def test_delete_note_success(client_no_middleware, db_session):
    """Test deleting a note"""
    # Setup user and create note
    user_data = {
        "email": "deleteuser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    note_data = {
        "title": "Note to Delete",
        "content": "This note will be deleted",
    }

    create_response = client_no_middleware.post(
        "/notes/", json=note_data, headers=headers
    )
    note_id = create_response.json()["data"]["id"]

    # Delete the note
    response = client_no_middleware.delete(
        f"/notes/{note_id}", headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Note deleted successfully"

    # Verify note is deleted
    get_response = client_no_middleware.get(
        f"/notes/{note_id}", headers=headers
    )
    assert get_response.status_code == 404


def test_delete_note_not_found(client_no_middleware, db_session):
    """Test deleting non-existent note returns 404"""
    user_data = {
        "email": "deletenotfound@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client_no_middleware.delete("/notes/99999", headers=headers)
    assert response.status_code == 404
    assert "Note not found" in response.json()["detail"]


def test_delete_note_unauthenticated(client_no_middleware):
    """Test deleting note without authentication returns 403"""
    response = client_no_middleware.delete("/notes/1")
    assert response.status_code == 403


def test_get_notes_stats_success(client_no_middleware, db_session):
    """Test getting notes statistics"""
    # Setup user and create notes
    user_data = {
        "email": "statsuser@example.com",
        "password": "password123",
    }

    register_response = client_no_middleware.post(
        "/auth/register", json=user_data
    )
    token = register_response.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create notes with different types and tags
    notes = [
        {
            "title": "Text Note",
            "content": "Simple text",
            "content_type": "text",
            "tags": ["work"],
        },
        {
            "title": "Markdown Note",
            "content": "# Markdown",
            "content_type": "markdown",
            "tags": ["docs", "work"],
        },
        {
            "title": "HTML Note",
            "content": "<p>HTML</p>",
            "content_type": "html",
            "tags": ["web"],
        },
    ]

    for note in notes:
        client_no_middleware.post("/notes/", json=note, headers=headers)

    # Get stats
    response = client_no_middleware.get(
        "/notes/stats/summary", headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "data" in data

    stats = data["data"]
    assert stats["total_notes"] == 3
    assert stats["total_words"] > 0
    assert "content_types" in stats
    assert "unique_tags" in stats
    assert stats["tags_count"] == 3  # work, docs, web


def test_get_notes_stats_unauthenticated(client_no_middleware):
    """Test getting notes stats without authentication returns 403"""
    response = client_no_middleware.get("/notes/stats/summary")
    assert response.status_code == 403


def test_notes_user_isolation(client_no_middleware, db_session):
    """Test that users can only access their own notes"""
    # Create two users
    user1_data = {"email": "user1@example.com", "password": "password123"}
    user2_data = {"email": "user2@example.com", "password": "password123"}

    user1_response = client_no_middleware.post(
        "/auth/register", json=user1_data
    )
    user2_response = client_no_middleware.post(
        "/auth/register", json=user2_data
    )

    user1_token = user1_response.json()["token"]["access_token"]
    user2_token = user2_response.json()["token"]["access_token"]

    user1_headers = {"Authorization": f"Bearer {user1_token}"}
    user2_headers = {"Authorization": f"Bearer {user2_token}"}

    # User 1 creates a note
    note_data = {"title": "User 1 Note", "content": "Private content"}
    create_response = client_no_middleware.post(
        "/notes/", json=note_data, headers=user1_headers
    )
    note_id = create_response.json()["data"]["id"]

    # User 2 tries to access User 1's note
    response = client_no_middleware.get(
        f"/notes/{note_id}", headers=user2_headers
    )
    assert (
        response.status_code == 404
    )  # Should not find note belonging to another user

    # User 2 tries to update User 1's note
    update_data = {"title": "Hacked Note"}
    response = client_no_middleware.put(
        f"/notes/{note_id}", json=update_data, headers=user2_headers
    )
    assert response.status_code == 404

    # User 2 tries to delete User 1's note
    response = client_no_middleware.delete(
        f"/notes/{note_id}", headers=user2_headers
    )
    assert response.status_code == 404
