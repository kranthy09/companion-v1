"""
companion/project/auth/models.py

Modern SQLAlchemy 2.0 User Model with all relationships
"""

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, DateTime, func
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from project.database import Base
from uuid import UUID, uuid4
from sqlalchemy.dialects.postgresql import UUID as PGUUID


if TYPE_CHECKING:
    from project.notes.models import Note
    from project.users.models import UserProfile, UserPreferences, UserActivity
    from project.tasks.models import TaskMetadata
    from project.blog.models import BlogPost


class User(Base):
    __tablename__ = "users"

    # Auto-incrementing primary key
    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    # Required fields
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255))  # Make nullable

    # Optional profile fields
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(20))

    # Status fields with defaults
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)

    # Auto-managed timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    notes: Mapped[List["Note"]] = relationship(
        "Note", back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    preferences: Mapped[Optional["UserPreferences"]] = relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    activities: Mapped[List["UserActivity"]] = relationship(
        "UserActivity", back_populates="user", cascade="all, delete-orphan"
    )
    tasks: Mapped[List["TaskMetadata"]] = relationship(
        "TaskMetadata", back_populates="user", cascade="all, delete-orphan"
    )
    blog_posts: Mapped[List["BlogPost"]] = relationship(
        "BlogPost", back_populates="author", cascade="all, delete-orphan"
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True
    )  # Supabase user ID

    @property
    def full_name(self) -> str:
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    blacklisted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime)
