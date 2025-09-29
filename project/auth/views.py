"""
project/auth/views.py - Authentication endpoints
"""

import secrets
import logging
from datetime import datetime
from fastapi import Response, Request, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt

from . import auth_router
from project.config import settings
from project.database import get_db_session
from project.auth.models import User
from project.auth.schemas import UserCreate, UserRead, Token, AuthResponse
from project.auth.utils import (
    verify_password,
    get_password_hash,
    create_token_pair,
    blacklist_token,
)
from project.auth.dependencies import get_current_active_user
from project.schemas.response import (
    APIResponse,
    success_response,
    error_response,
)

logger = logging.getLogger(__name__)


def set_auth_cookies(response: Response, access_token: str, csrf_token: str):
    """Helper to set auth cookies"""
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
    request: Request,
    response: Response,
    user_data: UserCreate,
    session: Session = Depends(get_db_session),
):
    """Register new user"""
    try:
        existing = (
            session.query(User).filter(User.email == user_data.email).first()
        )
        if existing:
            logger.warning(
                f"Registration attempt with existing email: {user_data.email}"
            )
            return error_response("Email already registered", request=request)

        user = User(
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        tokens = create_token_pair(user.email)
        csrf_token = secrets.token_urlsafe(32)

        set_auth_cookies(response, tokens["access_token"], csrf_token)

        logger.info(f"User registered successfully: {user.email}")

        return success_response(
            data=AuthResponse(
                user=UserRead.model_validate(user),
                token=Token(
                    access_token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"],
                ),
            ),
            message="Registration successful",
        )
    except Exception as e:
        logger.error(f"Registration failed: {str(e)}")
        session.rollback()
        raise HTTPException(500, "Registration failed")


@auth_router.post("/login", response_model=APIResponse[Token])
def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db_session),
):
    """Login with credentials"""
    try:
        user = (
            session.query(User)
            .filter(User.email == form_data.username)
            .first()
        )

        if not user or not verify_password(
            form_data.password, user.hashed_password
        ):
            logger.warning(f"Failed login attempt: {form_data.username}")
            return error_response("Invalid credentials", request=request)

        if not user.is_active:
            logger.warning(f"Inactive user login attempt: {user.email}")
            return error_response("Account is inactive", request=request)

        tokens = create_token_pair(user.email)
        csrf_token = secrets.token_urlsafe(32)

        set_auth_cookies(response, tokens["access_token"], csrf_token)

        logger.info(f"User logged in: {user.email}")

        return success_response(
            data=Token(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
            ),
            message="Login successful",
        )
    except Exception as e:
        logger.error(f"Login failed: {str(e)}")
        raise HTTPException(500, "Login failed")


@auth_router.post("/logout", response_model=APIResponse[dict])
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_active_user),
):
    """Logout and revoke token"""
    try:
        # Try to get token from cookie or header
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                token = auth_header.split(" ")[1]

        if token:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            exp = datetime.fromtimestamp(payload["exp"])
            blacklist_token(token, exp)

        response.delete_cookie(
            key="access_token", path="/", domain=settings.COOKIE_DOMAIN
        )
        response.delete_cookie(
            key="csrf_token", path="/", domain=settings.COOKIE_DOMAIN
        )

        logger.info(f"User logged out: {current_user.email}")

        return success_response(
            data={"logged_out": True},
            message="Logged out successfully",
        )
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        raise HTTPException(500, "Logout failed")
