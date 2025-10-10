"""
project/ollama/views.py
"""

import json
from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from . import ollama_router
from .service import ollama_service
from .tasks import (
    task_stream_enhance_note,
    task_stream_summarize_note,
    task_stream_summary,
)
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.database import get_db_session
from project.notes.models import Note, Quiz
from project.tasks.service import TaskService
from project.notes.schemas import QuestionCreate
from project.schemas.response import APIResponse, success_response
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


@ollama_router.post("/enhance/stream")
async def enhance_note_streaming(
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

    async def generate():
        yield f" \
            data: {json.dumps({'task_id': task.id, 'status': 'started'})}\n\n"

        prompt = f"""Improve and expand:
Title: {note.title}
Content: {note.content}
Enhanced:"""

        full_text = ""
        try:
            async for chunk in ollama_service.stream_generate(prompt):
                content = chunk.get("response", "")
                full_text += content
                yield f" \
                    data: {json.dumps({'chunk': content, 'done': False})}\n\n"

                if chunk.get("done"):
                    break

            from project.ollama.tasks import task_save_enhanced_note

            task_save_enhanced_note.delay(note.id, full_text)
            response = json.dumps(
                {
                    "chunk": "",
                    "done": True,
                    "full_text": full_text,
                    "task_id": task.id,
                }
            )

            yield f"data: {response}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@ollama_router.post("/summary/stream")
async def generate_summary_stream(
    note_request: NoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Generate summary with streaming"""
    note = (
        db.query(Note)
        .options(
            joinedload(Note.enhanced_versions),
            joinedload(Note.questions),
            joinedload(Note.quizzes).joinedload(Quiz.questions),
        )
        .filter(
            Note.id == note_request.note_id, Note.user_id == current_user.id
        )
        .first()
    )
    if not note:
        raise HTTPException(404, "Note not found")

    task = task_stream_summary.delay(note_request.note_id, current_user.id)

    async def generate():
        yield f" \
            data: {json.dumps({'task_id': task.id, 'status': 'started'})}\n\n"

        # Build context
        context_parts = []
        if note.enhanced_versions:
            context_parts.append(
                f"Enhanced: {note.enhanced_versions[0].content[:500]}"
            )
        if note.questions:
            qa = "\n".join(
                [
                    f"Q: {q.question_text}\nA: {q.answer}"
                    for q in note.questions[:5]
                ]
            )
            context_parts.append(f"Q&A:\n{qa}")
        if note.quizzes:
            topics = set()
            for quiz in note.quizzes:
                topics.update(
                    [q.question_text[:50] for q in quiz.questions[:3]]
                )
            context_parts.append(
                f"Quiz topics: {', '.join(list(topics)[:10])}"
            )

        context = (
            "\n\n".join(context_parts) if context_parts else note.content[:800]
        )

        prompt = f"""Create insightful summary with key takeaways.
Context: {context}

Must Provide:
1. Executive summary (2-3 sentences)
2. Top 3 key insights
3. Main conclusion

Summary:"""

        full_text = ""
        try:
            async for chunk in ollama_service.stream_generate(prompt):
                content = chunk.get("response", "")
                full_text += content
                yield f" \
                    data: {json.dumps({'chunk': content, 'done': False})}\n\n"

                if chunk.get("done"):
                    break

            from project.ollama.tasks import task_save_summary

            task_save_summary.delay(note.id, full_text)
            response = json.dumps(
                {
                    "chunk": "",
                    "done": True,
                    "full_text": full_text,
                    "task_id": task.id,
                }
            )
            yield f"data: {response}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@ollama_router.post(
    "/summarize/socket/stream", response_model=APIResponse[TaskResponse]
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
    """Ask question about note with streaming"""
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

            prompt = f"""Title: {note.title}
Content: {context}
Question: {request.question_text}

Provide clear explanation with up to 3 examples."""

            full_answer = ""
            async for chunk in ollama_service.stream_generate(prompt):
                content = chunk.get("response", "")
                full_answer += content
                yield f" \
                    data: {json.dumps({'chunk': content, 'done': False})}\n\n"

                if chunk.get("done"):
                    break

            from project.ollama.tasks import task_save_question

            task_save_question.delay(
                request.note_id, request.question_text, full_answer
            )
            response = json.dumps(
                {"chunk": "", "done": True, "full_answer": full_answer}
            )

            yield f"data: {response}\n\n"
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
