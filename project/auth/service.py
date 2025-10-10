"""
project/auth/service.py

User service layer for clean separation of business logic
"""

from typing import Optional
from uuid import UUID
import logging

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from fastapi import HTTPException, status

from project.auth.models import User
from project.auth.schemas import UserCreate, UserUpdate
from project.auth.supabase_client import supabase_admin

logger = logging.getLogger(__name__)


class UserService:
    """Service for user CRUD operations"""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by UUID"""
        return self.session.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return self.session.query(User).filter(User.email == email).first()

    def verify_supabase_token(self, token: str) -> dict:
        """Verify token with Supabase and return user data"""
        try:
            response = supabase_admin.auth.get_user(token)
            if not response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                )
            return {
                "id": response.user.id,
                "email": response.user.email,
                "email_confirmed": response.user.email_confirmed_at
                is not None,
            }
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed",
            )

    def create_from_supabase(
        self, supabase_user_id: str, user_data: UserCreate
    ) -> User:
        """Create user in local DB after Supabase registration"""
        try:
            existing = self.get_by_email(user_data.email)
            if existing:
                logger.info(f"User already exists: {user_data.email}")
                return existing

            user = User(
                id=UUID(supabase_user_id),
                email=user_data.email,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                phone=user_data.phone,
                is_active=True,
                is_superuser=False,
                is_verified=False,
            )

            self.session.add(user)
            self.session.commit()
            self.session.refresh(user)

            logger.info(f"User created: {user.email}")
            return user

        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"User creation failed - integrity error: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"User creation failed - database error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )

    def update(self, user_id: UUID, user_data: UserUpdate) -> User:
        """Update user information"""
        try:
            user = self.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            update_data = user_data.model_dump(exclude_unset=True)

            # Don't allow password updates (handled by Supabase)
            if "password" in update_data:
                del update_data["password"]
                logger.warning(
                    "Password update attempted via service - use Supabase"
                )

            for field, value in update_data.items():
                setattr(user, field, value)

            self.session.commit()
            self.session.refresh(user)

            logger.info(f"User updated: {user.email}")
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"User update failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )

    def soft_delete(self, user_id: UUID) -> User:
        """Soft delete user(deactivate)"""
        try:
            user = self.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            if user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot deactivate superuser",
                )

            user.is_active = False
            self.session.commit()
            self.session.refresh(user)

            logger.info(f"User deactivated: {user.email}")
            return user

        except HTTPException:
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"User deactivation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )

    def hard_delete(self, user_id: UUID) -> None:
        """Permanently delete user(use with caution)"""
        try:
            user = self.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )

            if user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cannot delete superuser",
                )

            self.session.delete(user)
            self.session.commit()

            logger.info(f"User permanently deleted: {user.email}")

        except HTTPException:
            raise
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"User deletion failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )
