"""
companion/project/users/views.py

User App APIs
"""

import logging

from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import users_router
from project.database import get_db_session
from project.auth.dependencies import (
    get_current_user,
)
from project.auth.models import User
from project.users.schemas import (
    UserProfileResponse,
)
from project.schemas.response import success_response, APIResponse


logger = logging.getLogger(__name__)


# Protected endpoints (authentication required)
@users_router.get("/profile", response_model=APIResponse[UserProfileResponse])
def get_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Get current user's profile information"""
    profile = UserProfileResponse.model_validate(current_user)

    return success_response(data=profile, message="Profile retrieved")


@users_router.delete("/delete-account")
def delete_account(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """
    Soft delete user account (deactivate instead of actual deletion)
    In production, you might want additional confirmation steps
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser accounts cannot be deleted via this endpoint",
        )

    # Instead of actual deletion, deactivate the account
    with session.begin():
        # You would update the user record here
        # current_user.is_active = False
        # session.add(current_user)
        pass

    return {
        "message": "Account deactivation requested",
        "user_id": str(current_user.id),
        "note": "This is a placeholder - implement actual deactivation logic",
    }
