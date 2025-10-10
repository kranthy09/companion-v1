"""
project/auth/views.py

Authentication endpoints using Supabase + service layer
"""

import secrets
import logging
from uuid import UUID

from fastapi import Response, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import auth_router
from project.config import settings
from project.database import get_db_session
from project.auth.models import User
from project.auth.schemas import (
    UserCreate,
    UserRead,
    LoginRequest,
    LoginResponse,
    SessionResponse,
    AuthResponse,
    Token,
)
from project.auth.service import UserService
from project.auth.supabase_client import supabase
from project.auth.dependencies import get_current_user
from project.schemas.response import APIResponse, success_response

logger = logging.getLogger(__name__)


def set_auth_cookies(
    response: Response, access_token: str, csrf_token: str
) -> None:
    """Set secure HttpOnly cookies for authentication"""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


@auth_router.post("/register", response_model=APIResponse[AuthResponse])
def register(
    response: Response,
    user_data: UserCreate,
    session: Session = Depends(get_db_session),
):
    """Register user via Supabase and sync to local DB"""
    try:
        # 1. Create in Supabase
        supabase_response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
        })

        if not supabase_response.user or not supabase_response.session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration failed",
            )

        # 2. Create in local DB via service
        user_service = UserService(session)
        user = user_service.create_from_supabase(
            supabase_response.user.id, user_data
        )

        # 3. Set secure cookies
        csrf_token = secrets.token_urlsafe(32)
        set_auth_cookies(
            response, supabase_response.session.access_token, csrf_token
        )

        logger.info(f"Registration successful: {user.email}")

        return success_response(
            data=AuthResponse(
                user=UserRead.model_validate(user),
                token=Token(
                    access_token=supabase_response.session.access_token,
                    refresh_token=supabase_response.session.refresh_token,
                ),
            ),
            message="Registration successful",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@auth_router.post("/login", response_model=APIResponse[LoginResponse])
def login(
    response: Response,
    credentials: LoginRequest,
    session: Session = Depends(get_db_session),
):
    """Login via Supabase"""
    try:
        # Authenticate with Supabase
        supabase_response = supabase.auth.sign_in_with_password({
            "email": credentials.username,
            "password": credentials.password,
        })

        if not supabase_response.session:
            raise HTTPException(401, "Invalid credentials")

        # Get or create user in local DB
        user_service = UserService(session)
        user = user_service.get_by_email(credentials.username)

        if not user:
            # Auto-create from Supabase
            logger.info(
                f"Auto-creating user from Supabase: {credentials.username}")
            user = User(
                id=UUID(supabase_response.user.id),
                email=credentials.username,
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        if not user.is_active:
            raise HTTPException(403, "Account is inactive")

        # Set cookies
        csrf_token = secrets.token_urlsafe(32)
        set_auth_cookies(
            response, supabase_response.session.access_token, csrf_token)

        logger.info(f"Login successful: {user.email}")

        return success_response(
            data=LoginResponse(
                access_token=supabase_response.session.access_token,
                refresh_token=supabase_response.session.refresh_token,
            ),
            message="Login successful",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(401, "Invalid credentials")


@auth_router.get("/session", response_model=APIResponse[SessionResponse])
def get_session(current_user: User = Depends(get_current_user)):
    """Get current authenticated session"""
    return success_response(
        data=SessionResponse(
            authenticated=True,
            user=UserRead.model_validate(current_user),
        ),
        message="Session active",
    )


@auth_router.post("/logout", response_model=APIResponse[dict])
def logout(response: Response):
    """Logout and clear cookies"""
    try:
        # Sign out from Supabase
        supabase.auth.sign_out()

        # Clear cookies
        response.delete_cookie(
            key="access_token", path="/", domain=settings.COOKIE_DOMAIN
        )
        response.delete_cookie(
            key="csrf_token", path="/", domain=settings.COOKIE_DOMAIN
        )

        logger.info("User logged out")

        return success_response(
            data={"logged_out": True},
            message="Logged out successfully",
        )

    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed",
        )


@auth_router.post("/refresh", response_model=APIResponse[LoginResponse])
def refresh_token(
    response: Response,
    refresh_token: str,
):
    """Refresh access token using refresh token"""
    try:
        supabase_response = supabase.auth.refresh_session(refresh_token)

        if not supabase_response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token refresh failed",
            )

        # Update cookie with new access token
        csrf_token = secrets.token_urlsafe(32)
        set_auth_cookies(
            response, supabase_response.session.access_token, csrf_token
        )

        return success_response(
            data=LoginResponse(
                access_token=supabase_response.session.access_token,
                refresh_token=supabase_response.session.refresh_token,
            ),
            message="Token refreshed",
        )

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token refresh failed",
        )
