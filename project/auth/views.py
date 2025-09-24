"""
companion/project/auth/views.py

Auth App user management APIs with refresh tokens
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel

from project.database import get_db_session
from project.auth.models import User
from project.auth.schemas import (
    UserCreate,
    UserRead,
    UserUpdate,
    Token,
    AuthResponse,
)
from project.auth.utils import (
    verify_password,
    get_password_hash,
    create_token_pair,
    verify_token,
)
from project.auth.dependencies import (
    get_current_active_user,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


@auth_router.post("/register", response_model=AuthResponse)
def register(
    user_data: UserCreate, session: Session = Depends(get_db_session)
):
    """Register new user with token pair"""
    existing_user = (
        session.query(User).filter(User.email == user_data.email).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        hashed_password=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        is_verified=user_data.is_verified or False,
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    tokens = create_token_pair(user.email)

    return AuthResponse(
        user=UserRead.model_validate(user),
        token=Token(access_token=tokens["access_token"]),
    )


@auth_router.post("/login", response_model=TokenPairResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db_session),
):
    """Login user and return token pair"""
    user = session.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(
        form_data.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    tokens = create_token_pair(user.email)
    return TokenPairResponse(**tokens)


@auth_router.post("/refresh", response_model=TokenPairResponse)
def refresh_token(
    request: RefreshTokenRequest, session: Session = Depends(get_db_session)
):
    """Get new access token using refresh token"""
    try:
        payload = verify_token(request.refresh_token, token_type="refresh")
        email = payload.get("sub")

        user = session.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        tokens = create_token_pair(user.email)
        return TokenPairResponse(**tokens)

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@auth_router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_active_user)):
    """Get current user"""
    return UserRead.from_orm(current_user)


@auth_router.put("/me", response_model=UserRead)
def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_db_session),
):
    """Update current user"""
    update_data = user_update.dict(exclude_unset=True)

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(
            update_data.pop("password")
        )

    for field, value in update_data.items():
        setattr(current_user, field, value)

    session.commit()
    session.refresh(current_user)

    return UserRead.from_orm(current_user)
