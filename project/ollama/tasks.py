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
from project.notes.models import (
    Note,
    Question,
    Quiz,
    QuizQuestion,
)
from project.notes.service import NoteService
from project.notes.schemas import QuizQuestionData, QuizGenerationResult
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


@shared_task(bind=True)
def task_stream_enhance_note(self, note_id: int, user_id: int):
    """Track streaming enhancement task"""
    self.update_state(state="STARTED", meta={"note_id": note_id})
    # Actual work done in streaming endpoint
    return {"note_id": note_id, "status": "streaming"}


@shared_task
def task_save_enhanced_note(note_id: int, content: str):
    """Save enhanced content as new version"""
    from project.notes.models import EnhancedNote
    from project.notes.service import NoteService

    with db_context() as session:
        service = NoteService(session)
        version = service.get_next_version_number(note_id)

        enhanced = EnhancedNote(
            note_id=note_id, content=content, version_number=version
        )
        session.add(enhanced)
        session.commit()
        return {"version": version}


@shared_task
def task_save_question(note_id: int, question_text: str, answer: str):
    """Save Q&A to database"""
    with db_context() as session:
        question = Question(
            note_id=note_id, question_text=question_text, answer=answer
        )
        session.add(question)
        session.commit()
        return {"question_id": question.id}


@shared_task(bind=True)
def task_stream_summary(self, note_id: int, user_id: int):
    self.update_state(state="STARTED", meta={"note_id": note_id})
    return {"note_id": note_id, "status": "streaming"}


@shared_task
def task_save_summary(note_id: int, content: str):
    from project.notes.models import NoteSummary

    with db_context() as session:
        summary = NoteSummary(note_id=note_id, content=content)
        session.add(summary)
        session.commit()
        return {"summary_id": summary.id}


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

                async for chunk in streaming_service.stream_content(
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


@shared_task
def task_generate_quiz(note_id: int, user_id: int) -> dict:
    try:
        with db_context() as session:
            note_service = NoteService(session)
            note = note_service.get_note_by_id(note_id, user_id)
            if not note:
                return {"error": "Note not found"}

            # Build context
            context = note.content[:500]
            if note.enhanced_versions:
                context += (
                    f"\n\nEnhanced: {note.enhanced_versions[0].content[:300]}"
                )

            prompt = f"""Create exactly 5 multiple choice questions.

Return ONLY a valid JSON array. No markdown, no explanations.

Format:
[{{"question":"text?","options":{{"A":"option","B":"option","C":"option","D":"option"}},"correct":"A","explanation":"why"}}]

Content: {context}

Important Instructions:
Proivde JSON with correct delimiters
Be minimalistic Yet powerful on generating valid JSON."""

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                ollama_service.generate(prompt, temperature=0.3)
            )
            loop.close()

            # Clean response
            response = result["response"].strip()
            response = (
                response.replace("```json", "").replace("```", "").strip()
            )

            # Extract JSON
            import re

            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if not json_match:
                logger.error(f"No JSON array found: {response[:200]}")
                return {"error": "Invalid format"}

            quiz_data = json.loads(json_match.group())

            if not isinstance(quiz_data, list) or len(quiz_data) == 0:
                return {"error": "Empty quiz"}

            # Save
            quiz = Quiz(note_id=note_id)
            session.add(quiz)
            session.flush()

            saved_count = 0
            for idx, q in enumerate(quiz_data, start=1):
                opts = q.get("options", {})
                if not isinstance(opts, dict) or len(opts) != 4:
                    continue
                if not all(k in opts for k in ["A", "B", "C", "D"]):
                    continue

                options_list = [f"{k}. {v}" for k, v in sorted(opts.items())]

                session.add(
                    QuizQuestion(
                        quiz_id=quiz.id,
                        question_text=q["question"],
                        options=options_list,
                        correct_answer=q["correct"],
                        explanation=q.get("explanation", ""),
                        order=idx,
                    )
                )
                saved_count += 1

            if saved_count == 0:
                session.rollback()
                return {"error": "No valid questions"}

            session.commit()

            # Return saved data
            saved_quiz = note_service.get_quiz_by_id(quiz.id, user_id)
            questions_response = [
                QuizQuestionData(
                    question_id=q.id,
                    question=q.question_text,
                    options={
                        opt.split(". ")[0]: opt.split(". ", 1)[1]
                        for opt in q.options
                    },
                ).model_dump()
                for q in saved_quiz.questions
            ]

            return QuizGenerationResult(
                quiz_id=saved_quiz.id,
                questions=questions_response,
                total=len(questions_response),
            ).model_dump()

    except json.JSONDecodeError as e:
        logger.error(f"JSON error at char {e.pos}: {str(e)}")
        return {"error": f"Parse failed: {str(e)}"}
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        return {"error": str(e)}
