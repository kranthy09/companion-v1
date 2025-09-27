"""
companion/project/ollama/views.py

Endpoints with SSE streaming support
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi.templating import Jinja2Templates


from . import ollama_router
from .service import ollama_service
from .streaming import streaming_service
from .tasks import task_enhance_note, task_summarize_note
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.database import get_db_session
from project.notes.models import Note

templates = Jinja2Templates(directory="project/ollama/templates")


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


@ollama_router.post("/enhance")
def enhance_note(
    request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Enhance note (background task - no streaming)"""
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
        "message": "Note enhancement queued",
        "note_id": request.note_id,
        "type": "enhance",
    }


@ollama_router.post("/summarize")
def summarize_note(
    request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Summarize note (background task - no streaming)"""
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
        "message": "Note summarization queued",
        "note_id": request.note_id,
        "type": "summary",
    }


@ollama_router.get("/stream/enhance/{note_id}")
async def stream_enhance_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Stream note enhancement in real-time (SSE)"""
    note = (
        db.query(Note)
        .filter(Note.id == note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    async def event_stream():
        async for chunk in streaming_service.stream_enhance_note(
            note.title, note.content, "improve"
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@ollama_router.get("/stream/summarize/{note_id}")
async def stream_summarize_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Stream note summary in real-time (SSE)"""
    note = (
        db.query(Note)
        .filter(Note.id == note_id, Note.user_id == current_user.id)
        .first()
    )

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Note not found"
        )

    async def event_stream():
        async for chunk in streaming_service.stream_enhance_note(
            note.title, note.content, "summary"
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@ollama_router.get("/task/{task_id}")
def get_task_status(
    task_id: str, current_user: User = Depends(get_current_user)
):
    """Check task status and get result"""
    from project.celery_utils import get_task_info

    return get_task_info(task_id)


@ollama_router.get("/stream-test")
def stream_test_page(request: Request):
    return templates.TemplateResponse("stream_test.html", {"request": request})
