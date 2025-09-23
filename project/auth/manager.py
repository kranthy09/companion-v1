import uuid
from typing import Optional
from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase

from project.auth.models import User
from project.config import settings


SECRET = (
    settings.SECRET_KEY
    if hasattr(settings, "SECRET_KEY")
    else "your-secret-key-change-this-in-production"
)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ):
        """Called after successful user registration"""
        print(f"User {user.id} has registered.")

        # You can add custom logic here, like:
        # - Send welcome email
        # - Create user profile
        # - Log registration event
        # - Trigger Celery task for post-registration processing

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
    ):
        """Called after successful login"""
        print(f"User {user.id} logged in.")

        # Custom logic like:
        # - Update last login timestamp
        # - Log login event
        # - Send login notification

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after password reset request"""
        print(
            f"User {user.id} has forgot their password. Reset token: {token}"
        )

        # Send password reset email
        # You can trigger a Celery task here

    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ):
        """Called after successful password reset"""
        print(f"User {user.id} has reset their password.")

    async def on_after_verification_request(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after email verification request"""
        print(
            f"Verification requested \
                for user {user.id}. Verification token: {token}"
        )

        # Send verification email
        # You can trigger a Celery task here

    async def on_after_verify(
        self, user: User, request: Optional[Request] = None
    ):
        """Called after successful email verification"""
        print(f"User {user.id} has been verified.")


async def get_user_db():
    """Get user database instance"""
    from project.database import SessionLocal

    session = SessionLocal()
    try:
        yield SQLAlchemyUserDatabase(session, User)
    finally:
        session.close()


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
):
    """Get user manager instance"""
    yield UserManager(user_db)
