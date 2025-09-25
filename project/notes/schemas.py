"""
companion/project/notes/schemas.py

Updated Notes schemas for integer IDs and modern Pydantic
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime


# Request Schemas
class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    content_type: str = Field(default="text", pattern="^(text|markdown|html)$")
    tags: Optional[List[str]] = Field(default_factory=list)

    @field_validator("title", "content")
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if v else v


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    content_type: Optional[str] = Field(None, pattern="^(text|markdown|html)$")
    tags: Optional[List[str]] = None

    @field_validator("title", "content")
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if v else v


# Response Schemas
class NoteBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int  # Changed from string to int
    title: str
    content: str
    content_type: str
    tags: List[str]
    has_ai_summary: bool
    ai_enhanced_content: Optional[str]
    created_at: datetime
    updated_at: datetime
    words_count: int


class NoteResponse(BaseModel):
    success: bool = True
    data: NoteBase
    message: Optional[str] = None


class NoteStatsBase(BaseModel):
    total_notes: int
    total_words: int
    content_types: dict
    unique_tags: List[str]
    tags_count: int


class NoteStatsReposne(BaseModel):
    success: bool = True
    data: NoteStatsBase
    message: Optional[str] = None


class NotesListResponse(BaseModel):
    success: bool = True
    data: List[NoteBase]
    total_count: int
    page: int = 1
    page_size: int = 20
    message: Optional[str] = None


class NoteDeleteResponse(BaseModel):
    success: bool = True
    message: str = "Note deleted successfully"


# Error Response
class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# Filter/Query Schemas
class NoteQueryParams(BaseModel):
    search: Optional[str] = None
    tags: Optional[List[str]] = None
    content_type: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(
        default="created_at", pattern="^(created_at|updated_at|title)$"
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")
