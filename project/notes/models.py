"""
companion/project/notes/models.py

Note Model in the app
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from project.database import Base


class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(50), default="text")  # text, markdown, etc.
    tags = Column(JSON, default=list)  # Store as JSON array
    has_ai_summary = Column(Boolean, default=False)
    ai_enhanced_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    words_count = Column(Integer, default=0)

    # Relationship - reference auth User model
    user = relationship("project.auth.models.User", backref="notes")

    def __init__(
        self,
        user_id,
        title,
        content,
        content_type="text",
        tags=None,
        *args,
        **kwargs
    ):
        self.user_id = user_id
        self.title = title
        self.content = content
        self.content_type = content_type
        self.tags = tags or []
        self.words_count = len(content.split()) if content else 0
        super().__init__(*args, **kwargs)

    @property
    def user_id_str(self):
        """Return user_id as string for serialization"""
        return str(self.user_id) if self.user_id else None

    def update_word_count(self):
        """Update word count based on current content"""
        self.words_count = len(self.content.split()) if self.content else 0
