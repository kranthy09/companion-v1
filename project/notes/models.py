"""
companion/project/notes/models.py

Updated Notes Model with separate AI fields
"""

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Integer,
)
from datetime import datetime
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
    has_ai_summary: Mapped[bool] = mapped_column(Boolean, default=False)
    has_ai_enhancement: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notes")

    @property
    def user_id_str(self) -> str:
        """Return user_id as string for serialization"""
        return str(self.user_id)

    def update_word_count(self) -> None:
        """Update word count based on current content"""
        self.words_count = len(self.content.split()) if self.content else 0

    def __repr__(self) -> str:
        return f"<Note(id={self.id}, title='{self.title[:30]}...')>"
