"""
companion/project/ollama/views.py

Complete endpoints: background + streaming
"""

from fastapi import Depends, HTTPException, status
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


class NoteRequest(BaseModel):
    note_id: int


@ollama_router.get("/health")
async def check_health():
    """Check Ollama status"""
    available = await ollama_service.health_check()
    return {
        "status": "healthy" if available else "unavailable",
        "available": available,
    }


# ============= Background Tasks (No Streaming) =============


@ollama_router.post("/enhance")
def enhance_note(
    request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Enhance note (background task)"""
    note = (
        db.query(Note)
        .filter(Note.id == request.note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    task = task_enhance_note.delay(request.note_id, current_user.id)

    return {
        "task_id": task.id,
        "message": "Enhancement queued",
        "note_id": request.note_id,
        "streaming": False,
    }


@ollama_router.post("/summarize")
def summarize_note(
    request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Summarize note (background task)"""
    note = (
        db.query(Note)
        .filter(Note.id == request.note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    task = task_summarize_note.delay(request.note_id, current_user.id)

    return {
        "task_id": task.id,
        "message": "Summary queued",
        "note_id": request.note_id,
        "streaming": False,
    }


# ============= Streaming Tasks =============


@ollama_router.post("/enhance/stream")
def enhance_note_streaming(
    request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Enhance note WITH streaming"""
    note = (
        db.query(Note)
        .filter(Note.id == request.note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    task = task_stream_enhance_note.delay(request.note_id, current_user.id)

    return {
        "task_id": task.id,
        "stream_channel": f"stream:{task.id}",
        "message": "Enhancement started with streaming",
        "note_id": request.note_id,
        "streaming": True,
        "ws_url": f"/ollama/ws/stream/{task.id}",
    }


@ollama_router.post("/summarize/stream")
def summarize_note_streaming(
    request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Summarize note WITH streaming"""
    note = (
        db.query(Note)
        .filter(Note.id == request.note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    task = task_stream_summarize_note.delay(request.note_id, current_user.id)

    return {
        "task_id": task.id,
        "stream_channel": f"stream:{task.id}",
        "message": "Summary started with streaming",
        "note_id": request.note_id,
        "streaming": True,
        "ws_url": f"/ollama/ws/stream/{task.id}",
    }


@ollama_router.get("/task/{task_id}")
def get_task_status(
    task_id: str, current_user: User = Depends(get_current_user)
):
    """Check task status"""
    from project.celery_utils import get_task_info

    return get_task_info(task_id)
