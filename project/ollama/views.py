"""
project/ollama/views.py - Enhanced with task metadata creation
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from . import ollama_router
from .service import ollama_service
from .tasks import (
    task_enhance_note,
    task_summarize_note,
    task_stream_enhance_note,
    task_stream_summarize_note,
)
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.database import get_db_session
from project.notes.models import Note
from project.tasks.service import TaskService
from project.schemas.response import (
    APIResponse,
    success_response,
)
from project.ollama.schemas import HealthCheckResponse, TaskResponse


class NoteRequest(BaseModel):
    note_id: int


@ollama_router.get("/health", response_model=APIResponse[HealthCheckResponse])
async def check_health(request: Request):
    """Check Ollama availability"""
    available = await ollama_service.health_check()
    return success_response(
        data=HealthCheckResponse(
            status="healthy" if available else "unavailable",
            available=available,
        )
    )


@ollama_router.post("/enhance", response_model=APIResponse[TaskResponse])
def enhance_note(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Enhance note (background)"""
    note = (
        db.query(Note)
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )

    if not note:
        raise HTTPException(404, "Note not found")

    # Queue Celery task
    task = task_enhance_note.delay(note_request.note_id, current_user.id)

    # Create task metadata
    task_service = TaskService(db)
    task_service.create_task(
        task_id=task.id,
        user_id=current_user.id,
        task_type="enhance",
        task_name=f"Enhance: {note.title[:50]}",
        resource_type="note",
        resource_id=note.id,
    )

    return success_response(
        data=TaskResponse(
            task_id=task.id,
            note_id=note_request.note_id,
            streaming=False,
            message="Enhancement queued",
        )
    )


@ollama_router.post("/summarize", response_model=APIResponse[TaskResponse])
def summarize_note(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Summarize note (background)"""
    note = (
        db.query(Note)
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )

    if not note:
        raise HTTPException(404, "Note not found")

    task = task_summarize_note.delay(note_request.note_id, current_user.id)

    task_service = TaskService(db)
    task_service.create_task(
        task_id=task.id,
        user_id=current_user.id,
        task_type="summarize",
        task_name=f"Summarize: {note.title[:50]}",
        resource_type="note",
        resource_id=note.id,
    )

    return success_response(
        data=TaskResponse(
            task_id=task.id,
            note_id=note_request.note_id,
            streaming=False,
            message="Summary queued",
        )
    )


@ollama_router.post(
    "/enhance/stream", response_model=APIResponse[TaskResponse]
)
def enhance_note_streaming(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Enhance note with streaming"""
    note = (
        db.query(Note)
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )

    if not note:
        raise HTTPException(404, "Note not found")

    task = task_stream_enhance_note.delay(
        note_request.note_id, current_user.id
    )

    task_service = TaskService(db)
    task_service.create_task(
        task_id=task.id,
        user_id=current_user.id,
        task_type="enhance_stream",
        task_name=f"Stream Enhance: {note.title[:50]}",
        resource_type="note",
        resource_id=note.id,
    )

    return success_response(
        data=TaskResponse(
            task_id=task.id,
            note_id=note_request.note_id,
            streaming=True,
            message="Enhancement started with streaming",
            stream_channel=f"stream:{task.id}",
            ws_url=f"/ollama/ws/stream/{task.id}",
        )
    )


@ollama_router.post(
    "/summarize/stream", response_model=APIResponse[TaskResponse]
)
def summarize_note_streaming(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Summarize note with streaming"""
    note = (
        db.query(Note)
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )

    if not note:
        raise HTTPException(404, "Note not found")

    task = task_stream_summarize_note.delay(
        note_request.note_id, current_user.id
    )

    task_service = TaskService(db)
    task_service.create_task(
        task_id=task.id,
        user_id=current_user.id,
        task_type="summarize_stream",
        task_name=f"Stream Summary: {note.title[:50]}",
        resource_type="note",
        resource_id=note.id,
    )

    return success_response(
        data=TaskResponse(
            task_id=task.id,
            note_id=note_request.note_id,
            streaming=True,
            message="Summary started with streaming",
            stream_channel=f"stream:{task.id}",
            ws_url=f"/ollama/ws/stream/{task.id}",
        )
    )
