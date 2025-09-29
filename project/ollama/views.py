"""
companion/project/ollama/views.py

Complete endpoints: background + streaming
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
from project.schemas.response import APIResponse, success_response
from project.ollama.schemas import (
    HealthCheckResponse,
    TaskResponse,
    TaskStatusResponse,
)


class NoteRequest(BaseModel):
    note_id: int


@ollama_router.get("/health", response_model=APIResponse[HealthCheckResponse])
async def check_health(request: Request):
    available = await ollama_service.health_check()
    data = HealthCheckResponse(
        status="healthy" if available else "unavailable", available=available
    )
    return success_response(data=data, request=request)


# ============= Background Tasks (No Streaming) =============


@ollama_router.post("/enhance", response_model=APIResponse[TaskResponse])
def enhance_note(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    note = (
        db.query(Note)
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )
    if not note:
        raise HTTPException(404, "Note not found")

    task = task_enhance_note.delay(note_request.note_id, current_user.id)
    data = TaskResponse(
        task_id=task.id,
        note_id=note_request.note_id,
        streaming=False,
        message="Enhancement queued",
    )
    return success_response(data=data, request=request_obj)


@ollama_router.post("/summarize", response_model=APIResponse[TaskResponse])
def summarize_note(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
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
    data = TaskResponse(
        task_id=task.id,
        note_id=note_request.note_id,
        streaming=False,
        message="Summary queued",
    )
    return success_response(data=data, request=request_obj)


# ============= Streaming Tasks =============


@ollama_router.post(
    "/enhance/stream", response_model=APIResponse[TaskResponse]
)
def enhance_note_streaming(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
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
    data = TaskResponse(
        task_id=task.id,
        note_id=note_request.note_id,
        streaming=True,
        message="Enhancement started with streaming",
        stream_channel=f"stream:{task.id}",
        ws_url=f"/ollama/ws/stream/{task.id}",
    )
    return success_response(data=data, request=request_obj)


@ollama_router.post(
    "/summarize/stream", response_model=APIResponse[TaskResponse]
)
def summarize_note_streaming(
    request_obj: Request,
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
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
    data = TaskResponse(
        task_id=task.id,
        note_id=note_request.note_id,
        streaming=True,
        message="Summary started with streaming",
        stream_channel=f"stream:{task.id}",
        ws_url=f"/ollama/ws/stream/{task.id}",
    )
    return success_response(data=data, request=request_obj)


@ollama_router.get(
    "/task/{task_id}", response_model=APIResponse[TaskStatusResponse]
)
def get_task_status(
    request: Request,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    from project.celery_utils import get_task_info

    info = get_task_info(task_id)
    data = TaskStatusResponse(**info)
    return success_response(data=data, request=request)
