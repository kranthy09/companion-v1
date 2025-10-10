"""
project/blog/schemas.py

Pydantic schemas for blog validation and serialization
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from uuid import UUID


class BlogStatus(str, Enum):
    """Blog post status enum"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SectionType(str, Enum):
    """Blog section types"""

    TEXT = "text"
    CODE = "code"
    QUOTE = "quote"
    IMAGE = "image"
    VIDEO = "video"
    HEADING = "heading"


# Base schemas
class BlogSectionBase(BaseModel):
    """Base schema for blog sections"""

    title: str = Field(..., max_length=255)
    content: str
    section_type: SectionType = SectionType.TEXT
    metadata: Dict[str, Any] = Field(default_factory=dict)
    order: int = 0


class BlogSectionCreate(BlogSectionBase):
    """Schema for creating a blog section"""

    pass


class BlogSectionUpdate(BaseModel):
    """Schema for updating a blog section"""

    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    section_type: Optional[SectionType] = None
    metadata: Optional[Dict[str, Any]] = None
    order: Optional[int] = None


class BlogSectionResponse(BlogSectionBase):
    """Response schema for blog section"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    created_at: datetime


# Blog post schemas
class BlogPostBase(BaseModel):
    """Base schema for blog posts"""

    title: str = Field(..., min_length=1, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    excerpt: Optional[str] = Field(None, max_length=500)
    content: str = Field(..., min_length=1)
    featured_image: Optional[str] = Field(None, max_length=500)
    category_id: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: List[str] = Field(default_factory=list)
    status: BlogStatus = BlogStatus.DRAFT
    is_featured: bool = False
    is_commentable: bool = True

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str, values) -> str:
        """Generate slug from title if not provided"""
        if not v and "title" in values.data:
            import re

            title = values.data["title"]
            # Convert to lowercase and replace spaces
            slug = title.lower().strip()
            # Remove special characters
            slug = re.sub(r"[^\w\s-]", "", slug)
            # Replace spaces with hyphens
            slug = re.sub(r"[-\s]+", "-", slug)
            return slug[:255]
        return v


class BlogPostCreate(BlogPostBase):
    """Schema for creating a blog post"""

    sections: Optional[List[BlogSectionCreate]] = None


class BlogPostUpdate(BaseModel):
    """Schema for updating a blog post"""

    title: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = Field(None, max_length=255)
    excerpt: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    featured_image: Optional[str] = Field(None, max_length=500)
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    meta_description: Optional[str] = Field(None, max_length=160)
    meta_keywords: Optional[List[str]] = None
    status: Optional[BlogStatus] = None
    is_featured: Optional[bool] = None
    is_commentable: Optional[bool] = None


class BlogPostResponse(BlogPostBase):
    """Response schema for blog post"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    author_id: int
    view_count: int
    read_time_minutes: int
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    # Nested relationships
    sections: Optional[List[BlogSectionResponse]] = None
    category: Optional[dict] = None
    comments_count: Optional[int] = None


class BlogPostList(BaseModel):
    """List response with pagination"""

    posts: List[BlogPostResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Category schemas
class BlogCategoryCreate(BaseModel):
    """Schema for creating a category"""

    name: str = Field(..., max_length=100)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    parent_id: Optional[int] = None


class BlogCategoryResponse(BaseModel):
    """Response schema for category"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: Optional[str]
    parent_id: Optional[int]
    posts_count: Optional[int] = 0


# Comment schemas
class BlogCommentCreate(BaseModel):
    """Schema for creating a comment"""

    content: str = Field(..., min_length=1)
    parent_id: Optional[int] = None


class BlogCommentResponse(BaseModel):
    """Response schema for comment"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    user_id: UUID
    content: str
    is_approved: bool
    created_at: datetime
    updated_at: datetime
    user: Optional[dict] = None
    replies: Optional[List["BlogCommentResponse"]] = None


# Query parameters
class BlogQueryParams(BaseModel):
    """Query parameters for filtering blog posts"""

    search: Optional[str] = None
    category_id: Optional[int] = None
    tags: Optional[List[str]] = None
    status: Optional[BlogStatus] = None
    author_id: Optional[int] = None
    is_featured: Optional[bool] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


# SSE streaming schemas
class SSEMessage(BaseModel):
    """Server-Sent Event message format"""

    event: Optional[str] = None
    data: str
    id: Optional[str] = None
    retry: Optional[int] = None


class BlogStreamChunk(BaseModel):
    """Chunk for blog content streaming"""

    post_id: int
    section_id: Optional[int] = None
    chunk_type: str  # 'title', 'content', 'section'
    content: str
    metadata: Optional[dict] = None
    is_complete: bool = False


class BlogGenerateRequest(BaseModel):
    """Request schema for blog generation"""

    blog_id: int
    enhancement_type: str = "improve"  # improve, expand, summarize


class BlogCreateStreamRequest(BaseModel):
    title: str
    content: str
