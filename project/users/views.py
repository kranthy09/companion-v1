"""
companion/project/users/views.py

User App APIs
"""

import logging
import random

import requests
from celery.result import AsyncResult
from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import users_router
from .schemas import UserBody
from .tasks import (
    sample_task,
    task_process_notification,
    task_send_welcome_email,
    task_add_subscribe,
)
from project.database import get_db_session
from project.auth.dependencies import (
    get_current_active_user,
    get_optional_user,
)
from project.auth.models import User
from project.users.schemas import (
    UserProfileResponse,
    TaskStatusResponse,
    MyTasksResponse,
)
from project.schemas.response import success_response, APIResponse


logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="project/users/templates")


def api_call(email: str):
    # used for testing a failed api call
    if random.choice([0, 1]):
        raise Exception("random processing error")

    # used for simulating a call to a third-party api
    requests.post("https://httpbin.org/delay/5")


# Public endpoints (no authentication required)
@users_router.get("/form/")
def form_example_get(request: Request):
    return templates.TemplateResponse(request, "form.html")


@users_router.post("/form/")
def form_example_post(user_body: UserBody):
    task = sample_task.delay(user_body.email)
    return JSONResponse({"task_id": task.task_id})


@users_router.get(
    "/task_status/", response_model=APIResponse[TaskStatusResponse]
)
def task_status(request: Request, task_id: str):
    task = AsyncResult(task_id)
    data = TaskStatusResponse(
        state=task.state,
        error=str(task.result) if task.state == "FAILURE" else None,
        result=task.result if task.state == "SUCCESS" else None,  # Add this
    )
    return success_response(data=data, request=request)


@users_router.get("/form_ws/")
def form_ws_example(request: Request):
    return templates.TemplateResponse(request, "form_ws.html")


@users_router.get("/form_socketio/")
def form_socketio_example(request: Request):
    return templates.TemplateResponse(request, "form_socketio.html")


# Public endpoint but enhanced with optional authentication
@users_router.post("/webhook_test_async/")
def webhook_test_async(current_user: User = Depends(get_optional_user)):
    task = task_process_notification.delay()

    response_data = {"task_id": task.id, "status": "Task queued"}

    if current_user:
        response_data["user_info"] = {
            "id": current_user.id,
            "email": current_user.email,
        }

    return response_data


# Protected endpoints (authentication required)
@users_router.get("/profile", response_model=APIResponse[UserProfileResponse])
def get_user_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """Get current user's profile information"""
    profile = UserProfileResponse.model_validate(current_user)

    return success_response(
        data=profile, message="Profile retrieved", request=request
    )


@users_router.get("/transaction_celery/")
def transaction_celery(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_db_session),
):
    """Protected endpoint that creates
    a Celery task for the authenticated user"""
    logger.info(
        f"User {current_user.id} {current_user.email}\
              triggered transaction_celery"
    )

    # Send welcome email task for the current user
    task_send_welcome_email.delay(str(current_user.id))

    return {
        "message": "Welcome email task queued",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
        },
    }


@users_router.post("/user_subscribe/")
def user_subscribe(
    user_body: UserBody,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_db_session),
):
    """
    Protected endpoint for user subscription
    Only authenticated users can subscribe other users or update their own info
    """

    # Check if the user is trying to
    # #subscribe themselves or has admin privileges
    if user_body.email != current_user.email and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only subscribe your own email or be a superuser",
        )

    # Update the current user's information if it's their own email
    if user_body.email == current_user.email:
        # You could update user info here if needed
        task_add_subscribe.delay(str(current_user.id))
        return {
            "message": "Subscription task sent successfully",
            "user": {"id": current_user.id, "email": current_user.email},
        }
    else:
        # Superuser subscribing another user - would need additional logic
        # For now, just queue the task with the current user's ID
        task_add_subscribe.delay(str(current_user.id))
        return {
            "message": "Subscription task sent successfully (as admin)",
            "target_email": user_body.email,
            "admin_user": str(current_user.id),
        }


@users_router.get("/my-tasks/", response_model=APIResponse[MyTasksResponse])
def get_my_tasks(
    request: Request, current_user: User = Depends(get_current_active_user)
):
    # Get recent tasks from Celery (requires task ID tracking in DB)
    # For now, return empty
    data = MyTasksResponse(
        user_id=current_user.id,
        email=current_user.email,
        message="Task list retrieved",
        tasks=[],
    )
    return success_response(data=data, request=request)


@users_router.delete("/delete-account")
def delete_account(
    current_user: User = Depends(get_current_active_user),
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
