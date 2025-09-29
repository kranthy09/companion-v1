"""
companion/project/users/schemas.py

User App API request and response schemas with modern Pydantic v2
"""

from datetime import datetime
from pydantic import BaseModel, HttpUrl, ConfigDict
from typing import Optional, Any


class UserProfileSchema(BaseModel):
    """Schema for extended user profile"""

    model_config = ConfigDict(from_attributes=True)

    bio: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    company: Optional[str] = None
    location: Optional[str] = None


class UserPreferencesSchema(BaseModel):
    """Schema for user preferences"""

    model_config = ConfigDict(from_attributes=True)

    email_notifications: Optional[int] = None  # 1=enabled, 0=disabled
    theme: Optional[str] = None  # "light", "dark"
    language: Optional[str] = None  # "en", "es", etc.
    timezone: Optional[str] = None  # "UTC", "America/New_York", etc.


class UserActivitySchema(BaseModel):
    """Schema for user activity logging"""

    model_config = ConfigDict(from_attributes=True)

    activity_type: str
    activity_data: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class UserBody(BaseModel):
    """Legacy schema - use auth schemas instead"""

    email: str
    username: Optional[str] = None


# Profile CRUD Schemas
class UserProfileCreate(BaseModel):
    bio: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    company: Optional[str] = None
    location: Optional[str] = None


class UserProfileUpdate(BaseModel):
    bio: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    company: Optional[str] = None
    location: Optional[str] = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    full_name: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


# Preferences CRUD Schemas
class UserPreferencesUpdate(BaseModel):
    email_notifications: Optional[int] = None
    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None


class UserPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    email_notifications: int
    theme: str
    language: str
    timezone: str


class TaskStatusResponse(BaseModel):
    state: str
    error: Optional[str] = None
    result: Optional[dict] = None
    result: Optional[Any] = None  # Add result field


class TaskQueueResponse(BaseModel):
    task_id: str
    message: str
    user_info: Optional[dict] = None


class MyTasksResponse(BaseModel):
    user_id: int
    email: str
    message: str
    tasks: list[dict]
