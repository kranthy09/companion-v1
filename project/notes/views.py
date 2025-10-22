"""Complete Notes API with comprehensive caching"""

from typing import List, Optional
from fastapi import Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from project.notes import notes_router
from project.notes.service import NoteService
from project.notes.schemas import (
    NoteCreate,
    NoteUpdate,
    NoteResponse,
    NoteQueryParams,
    EnhancedNoteResponse,
    QuestionBase,
    QuizWithSubmission,
    QuizQuestionWithSubmission,
    QuizAnswerSubmit,
    QuizResultDetail,
    QuizSubmitResponse,
    QuizGenerateResponse,
    NoteSummaryResponse,
    NoteMetaResponse,
)
from project.auth.dependencies import get_current_user
from project.auth.models import User
from project.database import get_db_session
from project.schemas.response import success_response
from project.middleware.cache import cache


async def invalidate_note_caches(user_id: str, note_id: int = None):
    """Helper to invalidate all note-related caches"""
    patterns = [
        f"notes_list:{user_id}:*",
        f"notes_stats:{user_id}",
    ]
    if note_id:
        patterns.extend(
            [
                f"note:{note_id}",
                f"note_meta:{note_id}",
                f"note_questions:{note_id}",
                f"note_enhanced:{note_id}",
                f"note_quizzes:{note_id}",
                f"note_summaries:{note_id}",
            ]
        )

    for pattern in patterns:
        await cache.delete(pattern)


@notes_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_note(
    note_data: NoteCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Create note and invalidate caches"""
    service = NoteService(db)
    note = service.create_note(current_user.id, note_data)

    # Invalidate list and stats caches
    background_tasks.add_task(invalidate_note_caches, str(current_user.id))

    return success_response(
        data=NoteResponse.model_validate(note),
        message="Note created successfully",
    )


@notes_router.get("/")
async def list_notes(
    search: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    content_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(
        "created_at", pattern="^(created_at|updated_at|title)$"
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List notes with 60s cache"""
    user_id = str(current_user.id)

    # Build cache key from query params
    cache_key = (
        f"notes_list:{user_id}:{page}:{page_size}:{sort_by}:{sort_order}"
    )
    if search:
        cache_key += f":search:{search}"
    if content_type:
        cache_key += f":type:{content_type}"
    if tags:
        cache_key += f":tags:{'_'.join(sorted(tags))}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=[NoteResponse(**n) for n in cached_data["notes"]],
            message=f"Found {cached_data['total']} notes",
            meta=cached_data["meta"],
        )

    # Cache miss - query DB
    query_params = NoteQueryParams(
        search=search,
        tags=tags,
        content_type=content_type,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    service = NoteService(db)
    notes, total = service.get_user_notes(current_user.id, query_params)

    # Prepare response
    notes_data = [NoteResponse.model_validate(n).model_dump() for n in notes]
    meta = {
        "total_count": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }

    # Cache for 60 seconds
    await cache.set(
        cache_key, {"notes": notes_data, "total": total, "meta": meta}, ttl=60
    )

    return success_response(
        data=[NoteResponse(**n) for n in notes_data],
        message=f"Found {total} notes",
        meta=meta,
    )


@notes_router.get("/stats/summary")
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get stats with 5min cache"""
    user_id = str(current_user.id)
    cache_key = f"notes_stats:{user_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=cached_data, message="Statistics retrieved"
        )

    # Cache miss
    service = NoteService(db)
    stats = service.get_user_notes_stats(current_user.id)

    # Cache for 5 minutes
    await cache.set(cache_key, stats, ttl=300)

    return success_response(data=stats, message="Statistics retrieved")


@notes_router.get("/{note_id}")
async def get_note(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get single note with 5min cache"""
    cache_key = f"note:{note_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=NoteResponse(**cached_data), message="Note retrieved"
        )

    # Cache miss
    service = NoteService(db)
    note = service.get_note_by_id(note_id, current_user.id)

    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    # Cache for 5 minutes
    note_data = NoteResponse.model_validate(note).model_dump()
    await cache.set(cache_key, note_data, ttl=300)

    return success_response(
        data=NoteResponse(**note_data), message="Note retrieved"
    )


@notes_router.put("/{note_id}")
async def update_note(
    note_id: int,
    note_data: NoteUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Update note and invalidate caches"""
    service = NoteService(db)
    note = service.update_note(note_id, current_user.id, note_data)

    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    # Invalidate all related caches
    background_tasks.add_task(
        invalidate_note_caches, str(current_user.id), note_id
    )

    return success_response(
        data=NoteResponse.model_validate(note), message="Note updated"
    )


@notes_router.delete("/{note_id}")
async def delete_note(
    note_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Delete note and invalidate caches"""
    service = NoteService(db)
    success = service.delete_note(note_id, current_user.id)

    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    # Invalidate all related caches
    background_tasks.add_task(
        invalidate_note_caches, str(current_user.id), note_id
    )

    return success_response(message="Note deleted")


@notes_router.get("/{note_id}/questions")
async def get_questions(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get questions with 10min cache"""
    cache_key = f"note_questions:{note_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(data=[QuestionBase(**q) for q in cached_data])

    # Cache miss
    service = NoteService(db)
    questions = service.get_note_questions(note_id, current_user.id)

    if questions is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    # Cache for 10 minutes
    questions_data = [
        QuestionBase.model_validate(q).model_dump() for q in questions
    ]
    await cache.set(cache_key, questions_data, ttl=600)

    return success_response(data=[QuestionBase(**q) for q in questions_data])


@notes_router.get("/{note_id}/enhanced")
async def get_enhanced(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get enhanced versions with 10min cache"""
    cache_key = f"note_enhanced:{note_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=[EnhancedNoteResponse(**v) for v in cached_data]
        )

    # Cache miss
    service = NoteService(db)
    versions = service.get_enhanced_versions(note_id, current_user.id)

    if versions is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    # Cache for 10 minutes
    versions_data = [
        EnhancedNoteResponse.model_validate(v).model_dump() for v in versions
    ]
    await cache.set(cache_key, versions_data, ttl=600)

    return success_response(
        data=[EnhancedNoteResponse(**v) for v in versions_data]
    )


@notes_router.get("/{note_id}/meta")
async def get_note_meta(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get metadata with 5min cache"""
    cache_key = f"note_meta:{note_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(data=NoteMetaResponse(**cached_data))

    # Cache miss
    service = NoteService(db)
    note = service.get_note_by_id(note_id, current_user.id)

    if not note:
        raise HTTPException(404, "Note not found")

    meta_data = {
        "enhanced_count": len(note.enhanced_versions),
        "quiz_count": len(note.quizzes),
        "question_count": len(note.questions),
        "summary_count": len(note.summaries),
    }

    # Cache for 5 minutes
    await cache.set(cache_key, meta_data, ttl=300)

    return success_response(data=NoteMetaResponse(**meta_data))


@notes_router.get("/summaries/{note_id}")
async def get_summaries(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get summaries with 10min cache"""
    cache_key = f"note_summaries:{note_id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=[NoteSummaryResponse(**s) for s in cached_data]
        )

    # Cache miss
    service = NoteService(db)
    summaries = service.get_note_summaries(note_id, current_user.id)

    if summaries is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    # Cache for 10 minutes
    summaries_data = [
        NoteSummaryResponse.model_validate(s).model_dump() for s in summaries
    ]
    await cache.set(cache_key, summaries_data, ttl=600)

    return success_response(
        data=[NoteSummaryResponse(**s) for s in summaries_data]
    )


@notes_router.post("/{note_id}/quiz/generate")
async def generate_quiz(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Generate quiz (no caching - task-based)"""
    service = NoteService(db)
    if not service.get_note_by_id(note_id, current_user.id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    from project.ollama.tasks import task_generate_quiz

    task = task_generate_quiz.delay(note_id, str(current_user.id))

    return success_response(
        data=QuizGenerateResponse(task_id=task.id),
        message="Quiz generation started",
    )


@notes_router.get("/{note_id}/quiz")
async def get_quizzes(
    note_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get quizzes with 5min cache"""
    cache_key = f"note_quizzes:{note_id}:{current_user.id}"

    # Try cache
    cached_data = await cache.get(cache_key)
    if cached_data:
        return success_response(
            data=[QuizWithSubmission(**q) for q in cached_data]
        )

    # Cache miss
    service = NoteService(db)
    note = service.get_note_with_quizzes_and_submissions(
        note_id, current_user.id
    )

    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")

    quizzes_data = []
    for quiz in note.quizzes:
        submission = quiz.submissions[0] if quiz.submissions else None

        questions = [
            QuizQuestionWithSubmission(
                id=q.id,
                question_text=q.question_text,
                options=q.options,
                user_answer=(
                    submission.answers.get(str(q.id)) if submission else None
                ),
                is_correct=(
                    submission.answers.get(str(q.id)) == q.correct_answer
                    if submission and str(q.id) in submission.answers
                    else None
                ),
            )
            for q in quiz.questions
        ]

        quizzes_data.append(
            QuizWithSubmission(
                id=quiz.id,
                created_at=quiz.created_at,
                questions=questions,
                submission=(
                    {
                        "score": submission.score,
                        "total": submission.total,
                        "submitted_at": submission.submitted_at,
                    }
                    if submission
                    else None
                ),
            ).model_dump()
        )

    # Cache for 5 minutes
    await cache.set(cache_key, quizzes_data, ttl=300)

    return success_response(
        data=[QuizWithSubmission(**q) for q in quizzes_data]
    )


@notes_router.post("/quiz/submit")
async def submit_quiz(
    submission: QuizAnswerSubmit,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Submit quiz and invalidate quiz cache"""
    service = NoteService(db)
    quiz = service.get_quiz_by_id(submission.quiz_id, current_user.id)

    if not quiz:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quiz not found")

    results = {}
    correct = 0
    stored_answers = {}

    for question in quiz.questions:
        user_answer = submission.answers.get(question.id)
        is_correct = user_answer == question.correct_answer

        if is_correct:
            correct += 1

        results[question.id] = QuizResultDetail(
            is_correct=is_correct,
            explanation=question.explanation if not is_correct else None,
        )
        stored_answers[str(question.id)] = user_answer

    service.create_quiz_submission(
        quiz_id=submission.quiz_id,
        answers=stored_answers,
        score=correct,
        total=len(quiz.questions),
    )

    # Invalidate quiz cache
    background_tasks.add_task(
        cache.delete, f"note_quizzes:*:{current_user.id}"
    )

    return success_response(
        data=QuizSubmitResponse(
            quiz_id=submission.quiz_id,
            correct_count=correct,
            total_count=len(quiz.questions),
            results=results,
        ),
        message=(
            "Perfect score!"
            if correct == len(quiz.questions)
            else "Quiz submitted"
        ),
    )


@notes_router.post("/batch", status_code=status.HTTP_201_CREATED)
async def batch_create(
    notes_data: List[NoteCreate],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Bulk create notes and invalidate caches"""
    if len(notes_data) > 100:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Max 100 notes per batch"
        )

    service = NoteService(db)
    notes = service.batch_create_notes(
        [n.model_dump() for n in notes_data], current_user.id
    )

    # Invalidate caches
    background_tasks.add_task(invalidate_note_caches, str(current_user.id))

    return success_response(
        data={"created_count": len(notes)},
        message=f"Created {len(notes)} notes",
    )


@notes_router.delete("/batch")
async def batch_delete(
    note_ids: List[int],
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Bulk delete notes and invalidate caches"""
    if len(note_ids) > 100:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Max 100 notes per batch"
        )

    service = NoteService(db)
    deleted = service.delete_notes_batch(note_ids, current_user.id)

    # Invalidate caches
    background_tasks.add_task(invalidate_note_caches, str(current_user.id))

    return success_response(
        data={"deleted_count": deleted}, message=f"Deleted {deleted} notes"
    )
