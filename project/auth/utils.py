"""
companion/project/auth/utils.py

Utility functions for JWT token management and Auth
"""

import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from project.config import settings

# Password hashing with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def create_refresh_token(
    data: dict, expires_delta: Optional[timedelta] = None
):
    """Create JWT refresh token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict:
    """Verify JWT token and return payload"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        if is_token_blacklisted(token):
            raise HTTPException(401, "Token has been revoked")

        # Check token type
        if payload.get("type") != token_type:
            raise credentials_exception

        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception

        return payload
    except JWTError:
        raise credentials_exception


def create_token_pair(email: str) -> Dict[str, str]:
    """Create both access and refresh tokens"""
    token_data = {"sub": email}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def blacklist_token(token: str, expires_at: datetime):
    from project.database import SessionLocal
    from project.auth.models import TokenBlacklist

    session = SessionLocal()
    blacklisted = TokenBlacklist(token=token, expires_at=expires_at)
    session.add(blacklisted)
    session.commit()
    session.close()


def is_token_blacklisted(token: str) -> bool:
    from project.database import SessionLocal
    from project.auth.models import TokenBlacklist

    session = SessionLocal()
    exists = (
        session.query(TokenBlacklist)
        .filter(TokenBlacklist.token == token)
        .first()
    )
    session.close()
    return exists is not None
