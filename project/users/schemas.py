from pydantic import BaseModel, HttpUrl
from typing import Optional


# Remove the old UserBody schema - user auth is
# # handled in project/auth/schemas.py
# This file now contains business logic schemas


class UserProfileSchema(BaseModel):
    """Schema for extended user profile"""

    bio: Optional[str] = None
    avatar_url: Optional[HttpUrl] = None
    website: Optional[HttpUrl] = None
    company: Optional[str] = None
    location: Optional[str] = None


class UserPreferencesSchema(BaseModel):
    """Schema for user preferences"""

    email_notifications: Optional[int] = None  # 1=enabled, 0=disabled
    theme: Optional[str] = None  # "light", "dark"
    language: Optional[str] = None  # "en", "es", etc.
    timezone: Optional[str] = None  # "UTC", "America/New_York", etc.


class UserActivitySchema(BaseModel):
    """Schema for user activity logging"""

    activity_type: str
    activity_data: Optional[dict] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


# Legacy schema for backward compatibility
class UserBody(BaseModel):
    """Legacy schema - use auth schemas instead"""

    email: str
    username: Optional[str] = None
