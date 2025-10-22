
from typing import Optional
from uuid import UUID
import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.orm import load_only

from project.database import get_db_session
from project.auth.models import User
from project.auth.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def _extract_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[str]:
    """Extract JWT from Bearer or cookie."""
    if credentials:
        return credentials.credentials
    return request.cookies.get("access_token")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        optional_security
    ),
    session: Session = Depends(get_db_session),
) -> User:
    """Verify Supabase JWT and fetch user from your tables."""
    try:
        token = _extract_token(request, credentials)
        logger.info(f"Token received: {token[:50]}...")  # First 50 chars
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )

        # Verify with Supabase
        response = supabase_admin.auth.get_user(token)
        logger.info(f"response: {response}")
        supabase_user = response.user

        if not supabase_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

        # Fetch from YOUR users table in same database
        user = session.query(User).options(
            load_only(
                User.id,
                User.email,
                User.is_active,
                User.is_verified
            )
        ).filter(User.id == UUID(supabase_user.id)).first()

        if not user:
            # Auto-create on first login
            # (triggered by Supabase webhook ideally)
            user = User(
                id=UUID(supabase_user.id),
                email=supabase_user.email,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info(f"Auto-created user: {user.email}")

        return user

    except ValueError as e:
        logger.warning(f"Auth error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication error",
        )


def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
