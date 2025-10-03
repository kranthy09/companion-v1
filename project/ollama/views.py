"""
project/ollama/views.py - Enhanced with task metadata creation
"""

import json
from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy.orm import joinedload

from project.notes.schemas import QuestionCreate

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
from project.ollama.streaming import streaming_service
from project.schemas.response import (
    APIResponse,
    success_response,
)
from project.ollama.schemas import HealthCheckResponse, TaskResponse
import logging

logger = logging.getLogger(__name__)


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


@ollama_router.post("/enhance/stream")
async def enhance_note_streaming(
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Start task and stream results"""
    note = (
        db.query(Note)
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )
    if not note:
        raise HTTPException(404, "Note not found")

    # Create Celery task for tracking
    task = task_stream_enhance_note.delay(
        note_request.note_id, current_user.id
    )
    task_id = task.id

    async def generate():
        # Send task_id first
        response = {"task_id": task_id, "status": "started"}
        yield f"data: {json.dumps(response)}\n\n"

        full_text = ""
        try:
            async for chunk in streaming_service.stream_enhance_note(
                note.title, note.content, "improve"
            ):
                full_text += chunk
                yield f" \
                    data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

            # Queue save task
            from project.ollama.tasks import task_save_enhanced_note

            task_save_enhanced_note.delay(note.id, full_text)
            response = {
                "chunk": "",
                "done": True,
                "full_text": full_text,
                "task_id": task_id,
            }
            yield f"data: {json.dumps(response)}\n\n"
        except Exception as e:
            # task.update_state(state="FAILURE", meta={"error": str(e)})
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


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


@ollama_router.post("/ask")
async def ask_question(
    request: QuestionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    note = (
        db.query(Note)
        .options(joinedload(Note.enhanced_versions))
        .filter(Note.id == request.note_id, Note.user_id == current_user.id)
        .first()
    )
    if not note:
        raise HTTPException(404, "Note not found")

    async def generate():
        try:
            context = (
                note.enhanced_versions[0].content
                if note.enhanced_versions
                else note.content
            )

            prompt = (
                f"Title: {note.title}\n\n"
                f"Content: {context}\n\n"
                f"Question: {request.question_text}\n\n"
                f"Provide clear explanation with up to 3 examples."
            )

            full_answer = ""
            async for chunk in streaming_service.stream_generate(prompt):
                full_answer += chunk
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

            # Queue save
            from project.ollama.tasks import task_save_question

            task_save_question.delay(
                request.note_id, request.question_text, full_answer
            )

            yield f"data: {json.dumps({'chunk': '', 'done': True, 'full_answer': full_answer})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
