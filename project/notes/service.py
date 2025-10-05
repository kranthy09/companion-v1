"""
companion/project/notes/service.py

Notes App, NoteService for note management in backend
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime
from project.notes.models import NoteSummary
from .models import Note, Quiz, QuizSubmission
from .schemas import NoteCreate, NoteUpdate, NoteQueryParams

logger = logging.getLogger(__name__)


class NoteService:
    """Service class for Note operations"""

    def __init__(self, db: Session):
        self.db = db

    def create_note(self, user_id: str, note_data: NoteCreate) -> Note:
        """Create a new note for a user"""
        print("user_id: ", user_id)
        word_count = len(note_data.content.split(" "))

        note = Note(
            user_id=user_id,
            title=note_data.title,
            content=note_data.content,
            content_type=note_data.content_type,
            tags=note_data.tags,
            words_count=word_count,
        )
        try:
            self.db.add(note)
            self.db.commit()
            self.db.refresh(note)
            return note
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create note: {e}")
            raise
        finally:
            self.db.close()

    def get_note_by_id(self, note_id: int, user_id: int) -> Optional[Note]:
        """Get a specific note by ID for a user"""
        return (
            self.db.query(Note)
            .filter(Note.id == note_id, Note.user_id == user_id)
            .first()
        )

    def get_user_notes(
        self, user_id: int, query_params: NoteQueryParams
    ) -> tuple[List[Note], int]:
        """Get paginated notes for a user with optional filters"""
        query = self.db.query(Note).filter(Note.user_id == user_id)

        # Apply search filter
        if query_params.search:
            search_term = f"%{query_params.search}%"
            query = query.filter(
                or_(
                    Note.title.ilike(search_term),
                    Note.content.ilike(search_term),
                )
            )

        # Apply content type filter
        if query_params.content_type:
            query = query.filter(
                Note.content_type == query_params.content_type
            )

        # Apply tags filter (match any of the provided tags)
        if query_params.tags:
            # Using JSON contains for PostgreSQL
            for tag in query_params.tags:
                query = query.filter(Note.tags.contains([tag]))

        # Get total count before pagination
        total_count = query.count()

        # Apply sorting
        sort_column = getattr(Note, query_params.sort_by)
        if query_params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # Apply pagination
        offset = (query_params.page - 1) * query_params.page_size
        notes = query.offset(offset).limit(query_params.page_size).all()

        return notes, total_count

    def update_note(
        self, note_id: int, user_id: int, note_data: NoteUpdate
    ) -> Optional[Note]:
        """Update an existing note"""
        note = self.get_note_by_id(note_id, user_id)
        if not note:
            return None

        # Update only provided fields
        if note_data.title is not None:
            note.title = note_data.title
        if note_data.content is not None:
            note.content = note_data.content
            note.update_word_count()
        if note_data.content_type is not None:
            note.content_type = note_data.content_type
        if note_data.tags is not None:
            note.tags = note_data.tags

        note.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_note(self, note_id: int, user_id: int) -> bool:
        """Delete a note"""
        note = self.get_note_by_id(note_id, user_id)
        if not note:
            return False

        self.db.delete(note)
        self.db.commit()
        return True

    def get_user_notes_stats(self, user_id: int) -> dict:
        """Get statistics about user's notes"""
        notes = self.db.query(Note).filter(Note.user_id == user_id).all()
        print("notes: ", notes)

        total_notes = len(notes)
        total_words = sum(note.words_count for note in notes)
        print("total words: ", total_words)

        # Count by content type
        content_types = {}
        for note in notes:
            content_types[note.content_type] = (
                content_types.get(note.content_type, 0) + 1
            )

        # Get all unique tags
        all_tags = set()
        for note in notes:
            if note.tags:
                all_tags.update(note.tags)

        return {
            "total_notes": total_notes,
            "total_words": total_words,
            "content_types": content_types,
            "unique_tags": list(all_tags),
            "tags_count": len(all_tags),
        }

    def get_note_questions(self, note_id: int, user_id: int) -> List:
        """Get all questions for a note"""

        note = self.get_note_by_id(note_id, user_id)
        if not note:
            return None
        return note.questions

    def get_enhanced_versions(self, note_id: int, user_id: int) -> List:
        note = (
            self.db.query(Note)
            .options(joinedload(Note.enhanced_versions))
            .filter(Note.id == note_id, Note.user_id == user_id)
            .first()
        )
        if not note:
            return None
        return note.enhanced_versions

    def get_next_version_number(self, note_id: int) -> int:
        """Get next version number for enhanced note"""
        from project.notes.models import EnhancedNote

        max_version = (
            self.db.query(func.max(EnhancedNote.version_number))
            .filter(EnhancedNote.note_id == note_id)
            .scalar()
        )
        return (max_version or 0) + 1

    def create_quiz_submission(
        self, quiz_id: int, answers: dict, score: int, total: int
    ):

        submission = QuizSubmission(
            quiz_id=quiz_id,
            score=score,
            total=total,
            answers=answers,
        )
        self.db.add(submission)
        self.db.commit()
        return submission

    def get_note_with_quizzes(self, note_id: int, user_id: int):
        """Get note with quizzes loaded"""

        return (
            self.db.query(Note)
            .options(joinedload(Note.quizzes).joinedload(Quiz.questions))
            .filter(Note.id == note_id, Note.user_id == user_id)
            .first()
        )

    def get_quiz_by_id(self, quiz_id: int, user_id: int):
        """Get quiz with questions for user's note"""

        return (
            self.db.query(Quiz)
            .options(joinedload(Quiz.questions))
            .join(Note)
            .filter(Quiz.id == quiz_id, Note.user_id == user_id)
            .first()
        )

    def get_note_with_quizzes_and_submissions(
        self, note_id: int, user_id: int
    ):
        """Get note"""

        note = (
            self.db.query(Note)
            .options(
                joinedload(Note.quizzes).joinedload(Quiz.questions),
                joinedload(Note.quizzes).joinedload(Quiz.submissions),
            )
            .filter(Note.id == note_id, Note.user_id == user_id)
            .first()
        )

        return note

    def get_note_summaries(self, note_id: int, user_id: int):
        """Note Summaries"""

        from project.notes.models import NoteSummary

        note = self.get_note_by_id(note_id, user_id)
        if not note:
            return None
        return (
            self.db.query(NoteSummary)
            .filter(NoteSummary.note_id == note_id)
            .order_by(NoteSummary.created_at.desc())
            .all()
        )

    def get_note_meta(self, note_id: int, user_id: int):
        """Note Meta, returns boolean for sections"""
        note = (
            self.db.query(Note)
            .options(
                joinedload(Note.enhanced_versions),
                joinedload(Note.questions),
                joinedload(Note.quizzes),
            )
            .filter(Note.id == note_id, Note.user_id == user_id)
            .first()
        )
        if not note:
            return None

        summaries = (
            self.db.query(NoteSummary)
            .filter(NoteSummary.note_id == note_id)
            .first()
        )

        return {
            "note_id": note_id,
            "has_enhanced_note": len(note.enhanced_versions) > 0,
            "has_quiz": len(note.quizzes) > 0,
            "has_question": len(note.questions) > 0,
            "has_summary": summaries is not None,
        }
