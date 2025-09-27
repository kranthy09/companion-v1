"""
companion/project/ollama/tasks.py

Celery tasks with WebSocket notifications
"""

import asyncio
from celery import shared_task
from celery.signals import task_postrun
from celery.utils.log import get_task_logger
from asgiref.sync import async_to_sync
from project.database import db_context
from project.notes.models import Note
from project.ollama.service import ollama_service

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def task_enhance_note(self, note_id: int, user_id: int, enhancement_type: str):
    """Enhance note using Ollama"""
    try:
        with db_context() as session:
            note = (
                session.query(Note)
                .filter(Note.id == note_id, Note.user_id == user_id)
                .first()
            )

            if not note:
                raise ValueError("Note not found")

            # Run async code in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                ollama_service.enhance_note(
                    note.title, note.content, enhancement_type
                )
            )
            loop.close()

            if not result["success"]:
                raise Exception(result.get("error", "Enhancement failed"))

            # Update note
            note.ai_enhanced_content = result["enhanced_content"]
            note.has_ai_summary = True
            session.commit()

            return {
                "note_id": note_id,
                "enhanced_content": result["enhanced_content"],
                "success": True,
                "enhancement_type": enhancement_type,
            }

    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise self.retry(exc=e, countdown=5)


@task_postrun.connect
def ollama_task_postrun_handler(task_id, **kwargs):
    """Send WebSocket update when task completes"""
    from project.ws.views import (
        update_celery_task_status,
        update_celery_task_status_socketio,
    )

    # WebSocket notification
    async_to_sync(update_celery_task_status)(task_id)

    # Socket.IO notification
    update_celery_task_status_socketio(task_id)
