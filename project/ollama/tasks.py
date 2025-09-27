"""
companion/project/ollama/tasks.py

Celery tasks with streaming support
"""

import asyncio
import json
from celery import shared_task
from celery.signals import task_postrun
from celery.utils.log import get_task_logger
from asgiref.sync import async_to_sync
from project.database import db_context
from project.notes.models import Note
from project.ollama.service import ollama_service
from project.ollama.streaming import streaming_service
from project import broadcast

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def task_enhance_note(self, note_id: int, user_id: int):
    """Enhance note (non-streaming background task)"""
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
                "enhanced_content": result["enhanced_content"],
            }

    except Exception as e:
        logger.error(f"Enhancement task failed: {e}")
        raise self.retry(exc=e, countdown=5)


@shared_task(bind=True, max_retries=3)
def task_summarize_note(self, note_id: int, user_id: int):
    """Summarize note (non-streaming background task)"""
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
                "summary": result["enhanced_content"],
            }

    except Exception as e:
        logger.error(f"Summary task failed: {e}")
        raise self.retry(exc=e, countdown=5)


@shared_task(bind=True, max_retries=3)
def task_stream_enhance_note(self, note_id: int, user_id: int):
    """Enhance note WITH streaming via WebSocket"""
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
                    note.title, note.content, "improve"
                ):
                    full_text += chunk
                    # Publish each chunk
                    await broadcast.publish(
                        channel=f"stream:{task_id}",
                        message=json.dumps(
                            {"type": "chunk", "data": chunk, "done": False}
                        ),
                    )

                # Final message
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
            note.ai_enhanced_content = full_text
            note.has_ai_enhancement = True
            session.commit()

            return {"note_id": note_id, "success": True, "content": full_text}

    except Exception as e:
        logger.error(f"Stream enhancement failed: {e}")
        raise self.retry(exc=e, countdown=5)


@shared_task(bind=True, max_retries=3)
def task_stream_summarize_note(self, note_id: int, user_id: int):
    """Summarize note WITH streaming via WebSocket"""
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
                    # Publish each chunk
                    await broadcast.publish(
                        channel=f"stream:{task_id}",
                        message=json.dumps(
                            {"type": "chunk", "data": chunk, "done": False}
                        ),
                    )

                # Final message
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

            return {"note_id": note_id, "success": True, "summary": full_text}

    except Exception as e:
        logger.error(f"Stream summary failed: {e}")
        raise self.retry(exc=e, countdown=5)


@task_postrun.connect
def ollama_task_postrun_handler(task_id, **kwargs):
    """Send WebSocket update when task completes"""
    from project.ws.views import (
        update_celery_task_status,
        update_celery_task_status_socketio,
    )

    async_to_sync(update_celery_task_status)(task_id)
    update_celery_task_status_socketio(task_id)
