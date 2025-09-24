"""
companion/project/users/models.py

User associated models in the User App.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UUID,
)

# from sqlalchemy.orm import relationship
from project.database import Base


class UserProfile(Base):
    """Extended user profile information"""

    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID, ForeignKey("users.id"), unique=True, nullable=False)

    # Extended profile fields
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    website = Column(String(200), nullable=True)
    company = Column(String(200), nullable=True)
    location = Column(String(200), nullable=True)

    # Relationship to auth User model
    # user = relationship("User", back_populates="profile")


class UserPreferences(Base):
    """User preferences and settings"""

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID, ForeignKey("users.id"), unique=True, nullable=False)

    # Preference fields
    email_notifications = Column(Integer, default=1)  # 1=enabled, 0=disabled
    theme = Column(String(20), default="light")
    language = Column(String(10), default="en")
    timezone = Column(String(50), default="UTC")


class UserActivity(Base):
    """Track user activities for analytics"""

    __tablename__ = "user_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=False)

    activity_type = Column(String(100), nullable=False)
    activity_data = Column(Text, nullable=True)  # JSON data
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default="now()")
