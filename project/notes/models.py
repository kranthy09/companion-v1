"""
companion/project/notes/models.py

Updated Notes Model with separate AI fields
"""

from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
)
from typing import Optional, List, TYPE_CHECKING

from project.database import Base

if TYPE_CHECKING:
    from project.auth.models import User


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Content fields
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(50), default="text")

    # Metadata
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    words_count: Mapped[int] = mapped_column(Integer, default=0)

    # AI Enhancement fields
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_enhanced_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notes")
    questions: Mapped[List["Question"]] = relationship(
        "Question", back_populates="note", cascade="all, delete-orphan"
    )
    enhanced_versions: Mapped[List["EnhancedNote"]] = relationship(
        "EnhancedNote",
        back_populates="note",
        cascade="all, delete-orphan",
        order_by="desc(EnhancedNote.version_number)",
    )
    quizzes: Mapped[List["Quiz"]] = relationship(
        "Quiz", back_populates="note", cascade="all, delete-orphan"
    )

    def update_word_count(self) -> None:
        """Update word count based on current content"""
        self.words_count = len(self.content.split()) if self.content else 0

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title[:30]}...')>"


class EnhancedNote(Base):
    __tablename__ = "enhanced_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"))
    content: Mapped[str] = mapped_column(Text)
    version_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    note: Mapped["Note"] = relationship(
        "Note", back_populates="enhanced_versions"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"))
    question_text: Mapped[str] = mapped_column(Text)
    answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    note: Mapped["Note"] = relationship("Note", back_populates="questions")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    note: Mapped["Note"] = relationship("Note", back_populates="quizzes")
    questions: Mapped[List["QuizQuestion"]] = relationship(
        "QuizQuestion", back_populates="quiz", cascade="all, delete-orphan"
    )
    submissions: Mapped[List["QuizSubmission"]] = relationship(
        "QuizSubmission", back_populates="quiz", cascade="all, delete-orphan"
    )


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[List[str]] = mapped_column(JSON)
    correct_answer: Mapped[str] = mapped_column(String(255))
    explanation: Mapped[str] = mapped_column(Text)

    quiz: Mapped["Quiz"] = relationship("Quiz", back_populates="questions")


class QuizSubmission(Base):
    __tablename__ = "quiz_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"))
    score: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(Integer)
    answers: Mapped[dict] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    quiz: Mapped["Quiz"] = relationship("Quiz")
