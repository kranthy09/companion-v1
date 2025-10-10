"""
project/blog/models.py

Production-grade Blog models with relationships
"""

from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    Boolean,
    Index,
    func,
)
from typing import Optional, List, TYPE_CHECKING

from project.database import Base

if TYPE_CHECKING:
    from project.auth.models import User


class BlogPost(Base):
    """Main blog post model with full features"""

    __tablename__ = "blog_posts"

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("blog_categories.id"), nullable=True
    )

    # Content fields
    title: Mapped[str] = mapped_column(String(255), index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    featured_image: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # Metadata
    tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    meta_description: Mapped[Optional[str]] = mapped_column(
        String(160), nullable=True
    )
    meta_keywords: Mapped[List[str]] = mapped_column(JSON, default=list)

    # Status and visibility
    status: Mapped[str] = mapped_column(
        String(20), default="draft", index=True
    )  # draft, published, archived
    is_featured: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )
    is_commentable: Mapped[bool] = mapped_column(Boolean, default=True)

    # Analytics
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    read_time_minutes: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    # Relationships
    author: Mapped["User"] = relationship("User", back_populates="blog_posts")
    category: Mapped[Optional["BlogCategory"]] = relationship(
        "BlogCategory", back_populates="posts"
    )
    comments: Mapped[List["BlogComment"]] = relationship(
        "BlogComment",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="desc(BlogComment.created_at)",
    )
    sections: Mapped[List["BlogSection"]] = relationship(
        "BlogSection",
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="BlogSection.order",
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_blog_status_published", "status", "published_at"),
        Index("idx_blog_author_status", "author_id", "status"),
        Index("idx_blog_category_status", "category_id", "status"),
    )

    def calculate_read_time(self) -> int:
        """Calculate estimated read time in minutes"""
        words = len(self.content.split()) if self.content else 0
        # Average reading speed: 200 words per minute
        return max(1, words // 200)

    def __repr__(self) -> str:
        return f"<BlogPost(id={self.id}, title='{self.title[:30]}...')>"


class BlogCategory(Base):
    """Blog categories for organization"""

    __tablename__ = "blog_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("blog_categories.id"), nullable=True
    )

    # Relationships
    posts: Mapped[List["BlogPost"]] = relationship(
        "BlogPost", back_populates="category"
    )
    children: Mapped[List["BlogCategory"]] = relationship(
        "BlogCategory", backref="parent", remote_side=[id]
    )

    def __repr__(self) -> str:
        return f"<BlogCategory(name='{self.name}')>"


class BlogComment(Base):
    """Comments on blog posts"""

    __tablename__ = "blog_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("blog_posts.id"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("blog_comments.id"), nullable=True
    )

    content: Mapped[str] = mapped_column(Text)
    is_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    post: Mapped["BlogPost"] = relationship(
        "BlogPost", back_populates="comments"
    )
    user: Mapped["User"] = relationship("User")
    replies: Mapped[List["BlogComment"]] = relationship(
        "BlogComment", backref="parent_comment", remote_side=[id]
    )

    def __repr__(self) -> str:
        return f"<BlogComment(id={self.id}, post_id={self.post_id})>"


class BlogSection(Base):
    """Sections within a blog post for structured content"""

    __tablename__ = "blog_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("blog_posts.id"), index=True
    )

    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    section_type: Mapped[str] = mapped_column(
        String(50), default="text"
    )  # text, code, quote, image, video
    jsonmeta: Mapped[dict] = mapped_column(JSON, default=dict)
    order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    post: Mapped["BlogPost"] = relationship(
        "BlogPost", back_populates="sections"
    )

    def __repr__(self) -> str:
        return f"<BlogSection(id={self.id}, title='{self.title[:30]}...')>"
