"""
project/ollama/tasks.py - Enhanced with task metadata tracking
"""

import asyncio
import json
from celery import shared_task
from celery.signals import task_prerun, task_postrun, task_failure
from celery.utils.log import get_task_logger
from asgiref.sync import async_to_sync

from project.database import db_context
from project.notes.models import Note
from project.ollama.service import ollama_service
from project.ollama.streaming import streaming_service
from project import broadcast

logger = get_task_logger(__name__)


@task_prerun.connect
def task_prerun_handler(task_id, task, args, kwargs, **extra):
    """Mark task as running when it starts"""
    from project.tasks.service import TaskService

    with db_context() as session:
        service = TaskService(session)
        service.update_task_status(task_id, "running")


@task_postrun.connect
def task_postrun_handler(task_id, task, args, kwargs, retval, **extra):
    """Update task metadata and broadcast status"""
    from project.tasks.service import TaskService
    from project.ws.views import (
        update_celery_task_status,
        update_celery_task_status_socketio,
    )

    with db_context() as session:
        service = TaskService(session)
        service.update_task_status(
            task_id,
            "success",
            result=(
                retval if isinstance(retval, dict) else {"result": str(retval)}
            ),
        )

    # Broadcast via WebSocket
    async_to_sync(update_celery_task_status)(task_id)
    update_celery_task_status_socketio(task_id)


@task_failure.connect
def task_failure_handler(task_id, exception, traceback, **extra):
    """Mark task as failed"""
    from project.tasks.service import TaskService

    with db_context() as session:
        service = TaskService(session)
        service.update_task_status(task_id, "failed", error=str(exception))


@shared_task(bind=True, max_retries=3)
def task_enhance_note(self, note_id: int, user_id: int):
    """Enhance note (background task)"""
    try:
        with db_context() as session:
            note = (
                session.query(Note)
                .filter(Note.id == note_id, Note.user_id == user_id)
                .first()
            )

            if not note:
                raise ValueError("Note not found")

            # Check Ollama availability
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            available = loop.run_until_complete(ollama_service.health_check())
            if not available:
                raise Exception("Ollama service unavailable")

            result = loop.run_until_complete(
                ollama_service.enhance_note(
                    note.title, note.content, "improve"
                )
            )
            loop.close()

            if not result["success"]:
                raise Exception(result.get("error", "Enhancement failed"))

            note.ai_enhanced_content = result["enhanced_content"]
            note.has_ai_enhancement = True
            session.commit()

            return {
                "note_id": note_id,
                "success": True,
                "type": "enhance",
                "content_length": len(result["enhanced_content"]),
            }

    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def task_summarize_note(self, note_id: int, user_id: int):
    """Summarize note (background task)"""
    try:
        with db_context() as session:
            note = (
                session.query(Note)
                .filter(Note.id == note_id, Note.user_id == user_id)
                .first()
            )

            if not note:
                raise ValueError("Note not found")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            available = loop.run_until_complete(ollama_service.health_check())
            if not available:
                raise Exception("Ollama service unavailable")

            result = loop.run_until_complete(
                ollama_service.enhance_note(
                    note.title, note.content, "summary"
                )
            )
            loop.close()

            if not result["success"]:
                raise Exception(result.get("error", "Summary failed"))

            note.ai_summary = result["enhanced_content"]
            note.has_ai_summary = True
            session.commit()

            return {
                "note_id": note_id,
                "success": True,
                "type": "summary",
                "summary_length": len(result["enhanced_content"]),
            }

    except Exception as e:
        logger.error(f"Summary failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True)
def task_stream_enhance_note(self, note_id: int, user_id: int):
    """Track streaming enhancement task"""
    self.update_state(state="STARTED", meta={"note_id": note_id})
    # Actual work done in streaming endpoint
    return {"note_id": note_id, "status": "streaming"}


@shared_task
def task_save_enhanced_note(note_id: int, content: str):
    """Save enhanced content to database"""
    with db_context() as session:
        note = session.query(Note).filter(Note.id == note_id).first()
        if note:
            note.ai_enhanced_content = content
            note.has_ai_enhancement = True
            session.commit()


@shared_task(bind=True, max_retries=3)
def task_stream_summarize_note(self, note_id: int, user_id: int):
    """Summarize note WITH streaming"""
    task_id = self.request.id

    try:
        with db_context() as session:
            note = (
                session.query(Note)
                .filter(Note.id == note_id, Note.user_id == user_id)
                .first()
            )

            if not note:
                raise ValueError("Note not found")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            full_text = ""

            async def stream_and_publish():
                nonlocal full_text
                await broadcast.connect()

                async for chunk in streaming_service.stream_enhance_note(
                    note.title, note.content, "summary"
                ):
                    full_text += chunk
                    await broadcast.publish(
                        channel=f"stream:{task_id}",
                        message=json.dumps(
                            {"type": "chunk", "data": chunk, "done": False}
                        ),
                    )

                await broadcast.publish(
                    channel=f"stream:{task_id}",
                    message=json.dumps(
                        {"type": "complete", "data": full_text, "done": True}
                    ),
                )

                await broadcast.disconnect()

            loop.run_until_complete(stream_and_publish())
            loop.close()

            # Save to DB
            note.ai_summary = full_text
            note.has_ai_summary = True
            session.commit()

            return {
                "note_id": note_id,
                "success": True,
                "summary_length": len(full_text),
            }

    except Exception as e:
        logger.error(f"Stream summary failed: {e}")
        raise self.retry(exc=e, countdown=60)
