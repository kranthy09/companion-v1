"""
project/auth/views.py - Enhanced with token rotation
"""

from datetime import datetime
from fastapi import Response, Request, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from . import auth_router
from project.config import settings
from project.database import get_db_session
from project.auth.models import User
from project.auth.schemas import UserCreate, UserRead, Token, AuthResponse
from project.auth.utils import (
    verify_password,
    get_password_hash,
    create_token_pair,
    verify_token,
    blacklist_token,
)
from project.auth.dependencies import get_current_active_user
from project.schemas.response import (
    success_response,
    error_response,
    APIResponse,
)
from project.schemas.errors import ErrorCode, ERROR_MESSAGES


class RefreshRequest(BaseModel):
    refresh_token: str


@auth_router.post("/register", response_model=APIResponse[AuthResponse])
def register(
    response: Response,
    user_data: UserCreate,
    session: Session = Depends(get_db_session),
):
    """Register new user"""
    if session.query(User).filter(User.email == user_data.email).first():
        return error_response(
            code=ErrorCode.VALIDATION_ERROR, message="Email already registered"
        )

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

    # Set HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
    )

    return success_response(
        data=AuthResponse(
            user=UserRead.model_validate(user), token=Token(**tokens)
        ),
        message="Registration successful",
    )


@auth_router.post("/login", response_model=APIResponse[Token])
def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db_session),
):
    """Login with token rotation"""
    user = session.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(
        form_data.password, user.hashed_password
    ):
        return error_response(
            code=ErrorCode.INVALID_CREDENTIALS,
            message=ERROR_MESSAGES[ErrorCode.INVALID_CREDENTIALS],
        )

    if not user.is_active:
        return error_response(
            code=ErrorCode.ACCOUNT_INACTIVE,
            message=ERROR_MESSAGES[ErrorCode.ACCOUNT_INACTIVE],
        )

    tokens = create_token_pair(user.email)

    # Set HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=settings.COOKIE_DOMAIN,
    )

    return success_response(data=Token(**tokens), message="Login successful")


@auth_router.post("/refresh", response_model=APIResponse[Token])
def refresh_token(
    response: Response,
    refresh_req: RefreshRequest,
    session: Session = Depends(get_db_session),
):
    """Refresh access token with rotation"""
    try:
        payload = verify_token(refresh_req.refresh_token, token_type="refresh")
        email = payload.get("sub")

        user = session.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            return error_response(
                code=ErrorCode.TOKEN_INVALID, message="Invalid refresh token"
            )

        # Blacklist old refresh token (rotation)
        exp = datetime.fromtimestamp(payload["exp"])
        blacklist_token(refresh_req.refresh_token, exp)

        # Issue new token pair
        tokens = create_token_pair(user.email)

        # Update cookie
        response.set_cookie(
            key="access_token",
            value=tokens["access_token"],
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            domain=settings.COOKIE_DOMAIN,
        )

        return success_response(
            data=Token(**tokens), message="Token refreshed"
        )

    except Exception:
        return error_response(
            code=ErrorCode.TOKEN_INVALID, message="Token refresh failed"
        )


@auth_router.post("/logout")
def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_active_user),
):
    """Logout and revoke token"""
    auth_header = request.headers.get("Authorization")

    if auth_header:
        token = auth_header.split(" ")[1]
        from jose import jwt

        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        exp = datetime.fromtimestamp(payload["exp"])
        blacklist_token(token, exp)

    # Clear cookie
    response.delete_cookie(key="access_token", domain=settings.COOKIE_DOMAIN)

    return success_response(message="Logged out successfully")


@auth_router.get("/session", response_model=APIResponse[dict])
def get_session(request: Request, session: Session = Depends(get_db_session)):
    """Check authentication status (for middleware)"""
    from project.auth.dependencies import get_optional_user

    user = get_optional_user(session=session)

    if not user:
        return success_response(data={"authenticated": False})

    return success_response(
        data={
            "authenticated": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
            },
        }
    )
