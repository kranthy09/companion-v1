"""
companion/project/users/models.py

Modern SQLAlchemy 2.0 User App Models
"""

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, DateTime, ForeignKey
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from project.database import Base

if TYPE_CHECKING:
    from project.auth.models import User


class UserProfile(Base):
    """Extended user profile information"""

    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    # Profile fields
    bio: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    website: Mapped[Optional[str]] = mapped_column(String(200))
    company: Mapped[Optional[str]] = mapped_column(String(200))
    location: Mapped[Optional[str]] = mapped_column(String(200))

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id})>"


class UserPreferences(Base):
    """User preferences and settings"""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    # Preference fields with defaults
    email_notifications: Mapped[int] = mapped_column(
        default=1
    )  # 1=enabled, 0=disabled
    theme: Mapped[str] = mapped_column(String(20), default="light")
    language: Mapped[str] = mapped_column(String(10), default="en")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="preferences")

    def __repr__(self) -> str:
        return (
            f"<UserPreferences(user_id={self.user_id}, theme='{self.theme}')>"
        )


class UserActivity(Base):
    """Track user activities for analytics"""

    __tablename__ = "user_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    activity_type: Mapped[str] = mapped_column(String(100))
    activity_data: Mapped[Optional[str]] = mapped_column(Text)  # JSON data
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default="now()"
    )

    # Relationship
    user: Mapped["User"] = relationship("User", back_populates="activities")

    def __repr__(self) -> str:
        return f"<UserActivity(user_id={self.user_id},\
              type='{self.activity_type}')>"
