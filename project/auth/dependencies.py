"""
companion/project/auth/dependencies.py

Fixed centralized auth dependencies for user authentication.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional
from jose import JWTError
from project.database import get_db_session
from project.auth.models import User
from project.auth.utils import verify_token
import logging

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_db_session),
) -> User:
    """Get current authenticated user"""
    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("sub")

        if not email:
            logger.warning("JWT token missing 'sub' claim")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing email claim",
            )

        user = session.query(User).filter(User.email == email).first()
        print("User: ", user)
        if not user:
            logger.warning(f"User not found for email: {email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Check if user is inactive AFTER finding them
        if not user.is_active:
            logger.warning(f"Inactive user attempted access: {email}")
            # Changed from 403 to 400
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account is inactive",
            )

        return user

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except JWTError as e:
        logger.warning(f"JWT validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error",
        )
    except Exception as e:
        logger.error(f"Unexpected error during authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error",
        )


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user (already verified in get_current_user)"""
    return current_user


def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current superuser"""
    if not current_user.is_superuser:
        logger.warning(
            f"Non-superuser attempted admin access: {current_user.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions - admin access required",
        )
    return current_user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        optional_security
    ),
    session: Session = Depends(get_db_session),
) -> Optional[User]:
    """Get user if authenticated, None otherwise (never raises exceptions)"""
    if not credentials:
        return None

    try:
        payload = verify_token(credentials.credentials)
        email = payload.get("sub")

        if not email:
            logger.debug("Optional auth: JWT token missing 'sub' claim")
            return None

        user = session.query(User).filter(User.email == email).first()
        if not user:
            logger.debug(f"Optional auth: User not found for email: {email}")
            return None

        if not user.is_active:
            logger.debug(f"Optional auth: Inactive user: {email}")
            return None

        return user

    except JWTError as e:
        logger.debug(f"Optional auth: JWT validation error: {str(e)}")
        return None
    except SQLAlchemyError as e:
        logger.error(f"Optional auth: Database error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Optional auth: Unexpected error: {str(e)}")
        return None


def get_user_from_token(
    token: str, session: Session, raise_on_error: bool = True
) -> Optional[User]:
    """
    Helper function to get user from token string
    Used internally by other auth functions
    """
    try:
        payload = verify_token(token)
        email = payload.get("sub")

        if not email:
            if raise_on_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing email",
                )
            return None

        user = session.query(User).filter(User.email == email).first()
        if not user:
            if raise_on_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found",
                )
            return None

        if not user.is_active:
            if raise_on_error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Account inactive",
                )
            return None

        return user

    except HTTPException:
        if raise_on_error:
            raise
        return None
    except JWTError as e:
        logger.debug(f"Token validation error: {str(e)}")
        if raise_on_error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return None
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        if raise_on_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database error",
            )
        return None
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if raise_on_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error",
            )
        return None


def require_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require user to be verified"""
    if not current_user.is_verified:
        logger.warning(
            f"Unverified user attempted verified access: {current_user.email}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return current_user
