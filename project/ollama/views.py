"""
companion/project/ollama/views.py

Basic Ollama API endpoints
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from . import ollama_router
from .service import ollama_service
from .tasks import task_enhance_note
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.database import get_db_session
from project.notes.models import Note


class EnhanceRequest(BaseModel):
    note_id: int
    enhancement_type: str = "summary"


@ollama_router.get("/health")
async def check_health():
    """Check Ollama status"""
    available = await ollama_service.health_check()
    return {
        "status": "healthy" if available else "unavailable",
        "available": available,
    }


@ollama_router.post("/enhance")
def enhance_note(
    request: EnhanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Enhance a note with AI"""
    # Verify note exists
    note = (
        db.query(Note)
        .filter(Note.id == request.note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    # Valid types
    if request.enhancement_type not in ["summary", "improve", "expand"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid enhancement type",
        )

    # Queue task
    task = task_enhance_note.delay(
        request.note_id, current_user.id, request.enhancement_type
    )

    return {
        "task_id": task.id,
        "message": "Enhancement queued",
        "note_id": request.note_id,
    }


@ollama_router.get("/task/{task_id}")
def get_task_status(
    task_id: str, current_user: User = Depends(get_current_user)
):
    """Check task status"""
    from project.celery_utils import get_task_info

    return get_task_info(task_id)
