# project/blog/models.py
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Integer,
    Boolean, Index
)
from sqlalchemy.dialects.postgresql import JSONB
import enum

from project.database import Base

if TYPE_CHECKING:
    from project.auth.models import User


class GenerationStatus(enum.Enum):
    """AI generation tracking states"""
    IDLE = "idle"
    GENERATING = "generating"
    COMPLETE = "complete"
    FAILED = "failed"


class BlogStatus(enum.Enum):
    """Publication states"""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SectionType(enum.Enum):
    """Unified section types"""
    TEXT = "text"
    CODE = "code"
    QUOTE = "quote"
    IMAGE = "image"
    VIDEO = "video"
    HEADING = "heading"
    INTRODUCTION = "introduction"
    BODY = "body"
    CONCLUSION = "conclusion"


class BlogPost(Base):
    __tablename__ = "blog_posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("blog_categories.id"), nullable=True
    )

    # Content
    title: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    featured_image: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True)

    # Metadata
    tags: Mapped[List[str]] = mapped_column(JSONB, default=list)
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(160), nullable=True)
    meta_keywords: Mapped[List[str]] = mapped_column(JSONB, default=list)

    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20), default="draft", index=True
    )
    generation_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, index=True
    )

    # AI tracking
    raw_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Visibility
    is_featured: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True)
    is_commentable: Mapped[bool] = mapped_column(Boolean, default=True)

    # Analytics
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    read_time_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    published_at: Mapped[Optional[datetime]
                         ] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="blog_posts")
    category: Mapped[Optional["BlogCategory"]] = relationship(
        "BlogCategory", back_populates="posts"
    )
    sections: Mapped[List["BlogSection"]] = relationship(
        "BlogSection",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="BlogSection.order",
    )
    comments: Mapped[List["BlogComment"]] = relationship(
        "BlogComment",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_blog_status_gen", "status", "generation_status"),
        Index("idx_blog_author_status", "author_id", "status"),
    )


class BlogSection(Base):
    __tablename__ = "blog_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("blog_posts.id"), index=True)

    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    section_type: Mapped[str] = mapped_column(
        String(50), default="text"
    )
    order: Mapped[int] = mapped_column(Integer, default=0)
    meta_info: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    post: Mapped["BlogPost"] = relationship(
        "BlogPost", back_populates="sections")


class BlogCategory(Base):
    __tablename__ = "blog_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    posts: Mapped[List["BlogPost"]] = relationship(
        "BlogPost", back_populates="category")


class BlogComment(Base):
    __tablename__ = "blog_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("blog_posts.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("blog_comments.id"), nullable=True
    )

    content: Mapped[str] = mapped_column(Text)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    post: Mapped["BlogPost"] = relationship(
        "BlogPost", back_populates="comments")
    user: Mapped["User"] = relationship("User")
    replies: Mapped[List["BlogComment"]] = relationship(
        "BlogComment", backref="parent_comment", remote_side=[id]
    )
