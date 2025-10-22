"""Production-optimized Notes Service with maximum performance"""

import logging
from typing import List, Optional, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, func, and_, or_, exists, case
from sqlalchemy.orm import Session, selectinload, load_only

from project.notes.models import (
    Note,
    NoteSummary,
    EnhancedNote,
    Question,
    Quiz,
    QuizSubmission,
)
from project.notes.schemas import NoteCreate, NoteUpdate, NoteQueryParams

logger = logging.getLogger(__name__)


class NoteService:
    """High-performance note service with optimized queries"""

    def __init__(self, db: Session):
        self.db = db
        self.db.expire_on_commit = False  # Performance optimization

    # ==================== CREATE ====================

    def create_note(self, user_id: UUID, note_data: NoteCreate) -> Note:
        """Create note with minimal DB round-trips"""
        note = Note(
            user_id=user_id,
            title=note_data.title,
            content=note_data.content,
            content_type=note_data.content_type,
            tags=note_data.tags,
            words_count=len(note_data.content.split()),
        )

        self.db.add(note)
        self.db.flush()  # Get ID without commit
        self.db.refresh(note)
        self.db.commit()
        return note

    def batch_create_notes(
        self, notes_data: List[dict], user_id: UUID
    ) -> List[Note]:
        """Bulk insert with single transaction"""
        notes = [
            Note(
                user_id=user_id,
                words_count=len(data.get("content", "").split()),
                **data,
            )
            for data in notes_data
        ]

        self.db.bulk_save_objects(notes, return_defaults=True)
        self.db.commit()
        return notes

    # ==================== READ ====================

    def get_note_by_id(
        self, note_id: int, user_id: UUID, load_relations: bool = False
    ) -> Optional[Note]:
        """Get note with optional eager loading"""
        query = select(Note).where(
            and_(Note.id == note_id, Note.user_id == user_id)
        )

        if load_relations:
            query = query.options(
                selectinload(Note.enhanced_versions),
                selectinload(Note.questions),
                selectinload(Note.quizzes),
                selectinload(Note.summaries),
            )

        return self.db.scalars(query).first()

    def get_user_notes(
        self, user_id: UUID, query_params: NoteQueryParams
    ) -> Tuple[List[Note], int]:
        """Optimized paginated query with window function for count"""

        # Base query with selective loading
        base_query = select(Note).where(Note.user_id == user_id)

        # Apply filters
        if query_params.search:
            search = f"%{query_params.search}%"
            base_query = base_query.where(
                or_(Note.title.ilike(search), Note.content.ilike(search))
            )

        if query_params.content_type:
            base_query = base_query.where(
                Note.content_type == query_params.content_type
            )

        if query_params.tags:
            for tag in query_params.tags:
                base_query = base_query.where(Note.tags.contains([tag]))

        # Get total count efficiently
        count_query = select(func.count()).select_from(base_query.subquery())
        total = self.db.scalar(count_query)

        # Apply sorting
        sort_col = getattr(Note, query_params.sort_by)
        base_query = base_query.order_by(
            sort_col.desc()
            if query_params.sort_order == "desc"
            else sort_col.asc()
        )

        # Load only needed columns for list view
        base_query = base_query.options(
            load_only(
                Note.id,
                Note.title,
                Note.content_type,
                Note.words_count,
                Note.created_at,
                Note.updated_at,
                Note.tags,
            )
        )

        # Paginate
        offset = (query_params.page - 1) * query_params.page_size
        notes = list(
            self.db.scalars(
                base_query.offset(offset).limit(query_params.page_size)
            )
        )

        return notes, total

    def get_user_notes_stats(self, user_id: UUID) -> dict:
        """Single optimized query for all stats"""

        # Aggregate stats in one query
        result = self.db.execute(
            select(
                func.count(Note.id).label("total_notes"),
                func.coalesce(func.sum(Note.words_count), 0).label(
                    "total_words"
                ),
                func.count(case((Note.content_type == "text", 1))).label(
                    "text"
                ),
                func.count(case((Note.content_type == "markdown", 1))).label(
                    "markdown"
                ),
                func.count(case((Note.content_type == "html", 1))).label(
                    "html"
                ),
            ).where(Note.user_id == user_id)
        ).first()

        # Get unique tags efficiently
        tags_result = self.db.execute(
            select(
                func.array_agg(func.distinct(func.unnest(Note.tags)))
            ).where(and_(Note.user_id == user_id, Note.tags.isnot(None)))
        ).scalar()

        unique_tags = sorted(tags_result) if tags_result else []

        return {
            "total_notes": result.total_notes or 0,
            "total_words": result.total_words or 0,
            "content_types": {
                "text": result.text or 0,
                "markdown": result.markdown or 0,
                "html": result.html or 0,
            },
            "unique_tags": unique_tags,
            "tags_count": len(unique_tags),
        }

    # ==================== RELATIONSHIPS ====================

    def get_note_questions(
        self, note_id: int, user_id: UUID
    ) -> Optional[List[Question]]:
        """Get questions with single query"""
        result = self.db.execute(
            select(Question)
            .join(Note)
            .where(and_(Note.id == note_id, Note.user_id == user_id))
            .order_by(Question.created_at.desc())
        )

        questions = list(result.scalars())
        return questions if questions else None

    def get_enhanced_versions(
        self, note_id: int, user_id: UUID
    ) -> Optional[List[EnhancedNote]]:
        """Get enhanced versions efficiently"""
        result = self.db.execute(
            select(EnhancedNote)
            .join(Note)
            .where(and_(Note.id == note_id, Note.user_id == user_id))
            .order_by(EnhancedNote.version_number.desc())
        )

        versions = list(result.scalars())
        return versions if versions else None

    def get_note_summaries(
        self, note_id: int, user_id: UUID
    ) -> Optional[List[NoteSummary]]:
        """Get summaries efficiently"""
        # Verify ownership first
        exists_query = (
            select(1)
            .where(and_(Note.id == note_id, Note.user_id == user_id))
            .limit(1)
        )

        if not self.db.scalar(exists_query):
            return None

        result = self.db.execute(
            select(NoteSummary)
            .where(NoteSummary.note_id == note_id)
            .order_by(NoteSummary.created_at.desc())
        )

        return list(result.scalars())

    # ==================== METADATA ====================

    def get_note_meta_optimized(
        self, note_id: int, user_id: UUID
    ) -> Optional[dict]:
        """Ultra-fast metadata with EXISTS subqueries"""

        result = self.db.execute(
            select(
                Note.id,
                exists(select(1).where(EnhancedNote.note_id == note_id)).label(
                    "has_enhanced"
                ),
                exists(select(1).where(Quiz.note_id == note_id)).label(
                    "has_quiz"
                ),
                exists(select(1).where(Question.note_id == note_id)).label(
                    "has_question"
                ),
                exists(select(1).where(NoteSummary.note_id == note_id)).label(
                    "has_summary"
                ),
                # Get counts in same query
                select(func.count(EnhancedNote.id))
                .where(EnhancedNote.note_id == note_id)
                .scalar_subquery()
                .label("enhanced_count"),
                select(func.count(Quiz.id))
                .where(Quiz.note_id == note_id)
                .scalar_subquery()
                .label("quiz_count"),
                select(func.count(Question.id))
                .where(Question.note_id == note_id)
                .scalar_subquery()
                .label("question_count"),
                select(func.count(NoteSummary.id))
                .where(NoteSummary.note_id == note_id)
                .scalar_subquery()
                .label("summary_count"),
            ).where(and_(Note.id == note_id, Note.user_id == user_id))
        ).first()

        if not result:
            return None

        return {
            "note_id": result.id,
            "has_enhanced_note": result.has_enhanced,
            "has_quiz": result.has_quiz,
            "has_question": result.has_question,
            "has_summary": result.has_summary,
            "enhanced_count": result.enhanced_count or 0,
            "quiz_count": result.quiz_count or 0,
            "question_count": result.question_count or 0,
            "summary_count": result.summary_count or 0,
        }

    # ==================== QUIZ ====================

    def get_quiz_by_id(self, quiz_id: int, user_id: UUID) -> Optional[Quiz]:
        """Get quiz with questions in single query"""
        result = self.db.execute(
            select(Quiz)
            .options(selectinload(Quiz.questions))
            .join(Note)
            .where(and_(Quiz.id == quiz_id, Note.user_id == user_id))
        )

        return result.scalar_one_or_none()

    def get_note_with_quizzes_and_submissions(
        self, note_id: int, user_id: UUID
    ) -> Optional[Note]:
        """Optimized quiz loading with submissions"""
        result = self.db.execute(
            select(Note)
            .options(
                selectinload(Note.quizzes).selectinload(Quiz.questions),
                selectinload(Note.quizzes).selectinload(Quiz.submissions),
            )
            .where(and_(Note.id == note_id, Note.user_id == user_id))
        )

        return result.scalar_one_or_none()

    def create_quiz_submission(
        self, quiz_id: int, answers: dict, score: int, total: int
    ) -> QuizSubmission:
        """Create submission efficiently"""
        submission = QuizSubmission(
            quiz_id=quiz_id,
            score=score,
            total=total,
            answers=answers,
            submitted_at=datetime.utcnow(),
        )

        self.db.add(submission)
        self.db.commit()
        return submission

    def get_next_version_number(self, note_id: int) -> int:
        """Get next version with single query"""
        max_version = self.db.scalar(
            select(
                func.coalesce(func.max(EnhancedNote.version_number), 0)
            ).where(EnhancedNote.note_id == note_id)
        )

        return max_version + 1

    # ==================== UPDATE ====================

    def update_note(
        self, note_id: int, user_id: UUID, note_data: NoteUpdate
    ) -> Optional[Note]:
        """Update with optimized query"""

        # Build update dict
        update_data = note_data.model_dump(exclude_unset=True)
        if not update_data:
            return self.get_note_by_id(note_id, user_id)

        # Update word count if content changed
        if "content" in update_data:
            update_data["words_count"] = len(update_data["content"].split())

        update_data["updated_at"] = datetime.utcnow()

        # Execute update
        stmt = (
            Note.__table__.update()
            .where(and_(Note.id == note_id, Note.user_id == user_id))
            .values(**update_data)
        )

        result = self.db.execute(stmt)

        if result.rowcount == 0:
            return None

        self.db.commit()
        return self.get_note_by_id(note_id, user_id)

    # ==================== DELETE ====================

    def delete_note(self, note_id: int, user_id: UUID) -> bool:
        """Delete with single query"""
        stmt = Note.__table__.delete().where(
            and_(Note.id == note_id, Note.user_id == user_id)
        )

        result = self.db.execute(stmt)
        self.db.commit()

        return result.rowcount > 0

    def delete_notes_batch(self, note_ids: List[int], user_id: UUID) -> int:
        """Bulk delete with single query"""
        stmt = Note.__table__.delete().where(
            and_(Note.id.in_(note_ids), Note.user_id == user_id)
        )

        result = self.db.execute(stmt)
        self.db.commit()

        return result.rowcount

    # ==================== UTILITY ====================

    def note_exists(self, note_id: int, user_id: UUID) -> bool:
        """Fast existence check"""
        return self.db.scalar(
            select(
                exists().where(
                    and_(Note.id == note_id, Note.user_id == user_id)
                )
            )
        )
