# project/blog/schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


# Generation schemas
class GenerateRequest(BaseModel):
    """Start streaming generation"""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)


class GenerateCompleteRequest(BaseModel):
    """Complete generation with full text"""
    post_id: int


# Post schemas
class PostCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str
    excerpt: Optional[str] = None


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    status: Optional[str] = None


class SectionResponse(BaseModel):
    """Response schema for blog section"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    title: Optional[str]
    content: str
    section_type: str
    order: int
    meta_info: dict = Field(default_factory=dict)
    created_at: datetime


class PostResponse(BaseModel):
    """Response schema for blog post with sections"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    excerpt: Optional[str]
    content: str
    status: str
    generation_status: Optional[str]
    view_count: int
    read_time_minutes: int
    created_at: datetime
    updated_at: datetime
    sections: List[SectionResponse] = Field(default_factory=list)


class PostResponseData(BaseModel):
    success: bool = True
    data: PostResponse
    message: Optional[str] = None
