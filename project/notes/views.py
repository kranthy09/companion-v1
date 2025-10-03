"""
companion/project/notes/views.py

Notes App APIs
"""

from fastapi import Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from project.schemas.response import APIResponse, success_response

from . import notes_router
from .schemas import (
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NotesListResponse,
    NoteDeleteResponse,
    NoteQueryParams,
    NoteStatsResponse,
    QuestionBase,
)
from .service import NoteService
from project.auth.dependencies import (
    get_current_user,
)  # Use existing auth
from project.auth.models import User  # Use auth User model
from project.database import get_db_session


@notes_router.post(
    "/", response_model=NoteResponse, status_code=status.HTTP_201_CREATED
)
def create_note(
    note_data: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create a new note for the authenticated user"""
    try:
        service = NoteService(db)
        note = service.create_note(current_user.id, note_data)
        return NoteResponse(
            success=True, data=note, message="Note created successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@notes_router.get("/", response_model=NotesListResponse)
def list_notes(
    search: Optional[str] = Query(
        None, description="Search in title and content"
    ),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    content_type: Optional[str] = Query(
        None, description="Filter by content type"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query(
        "created_at", pattern="^(created_at|updated_at|title)$"
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get paginated list of notes for the authenticated user"""
    try:
        query_params = NoteQueryParams(
            search=search,
            tags=tags,
            content_type=content_type,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        service = NoteService(db)
        notes, total_count = service.get_user_notes(
            current_user.id, query_params
        )

        return NotesListResponse(
            success=True,
            data=notes,
            total_count=total_count,
            page=page,
            page_size=page_size,
            message=f"Found {total_count} notes",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@notes_router.get("/{note_id}", response_model=NoteResponse)
def get_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a specific note by ID"""
    service = NoteService(db)
    note = service.get_note_by_id(note_id, current_user.id)

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    return NoteResponse(
        success=True, data=note, message="Note retrieved successfully"
    )


@notes_router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int,
    note_data: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update an existing note"""
    try:
        service = NoteService(db)
        note = service.update_note(note_id, current_user.id, note_data)

        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
            )

        return NoteResponse(
            success=True, data=note, message="Note updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@notes_router.delete("/{note_id}", response_model=NoteDeleteResponse)
def delete_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete a note"""
    service = NoteService(db)
    success = service.delete_note(note_id, current_user.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    return NoteDeleteResponse(
        success=True, message="Note deleted successfully"
    )


@notes_router.get("/stats/summary", response_model=NoteStatsResponse)
def get_notes_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get statistics about user's notes"""
    service = NoteService(db)
    stats = service.get_user_notes_stats(current_user.id)
    print("Stats: ", stats)

    return NoteStatsResponse(
        success=True,
        data=stats,
        message="Statistics retrieved successfully",
    )


@notes_router.get(
    "/{note_id}/questions", response_model=APIResponse[List[QuestionBase]]
)
def get_note_questions(
    request: Request,
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service = NoteService(db)
    questions = service.get_note_questions(note_id, current_user.id)

    if questions is None:
        raise HTTPException(404, "Note not found")

    questions_data = [QuestionBase.model_validate(q) for q in questions]
    return success_response(data=questions_data)
