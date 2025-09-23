from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users import FastAPIUsers

from project.auth.models import User
from project.auth.manager import get_user_manager
from project.config import settings
import uuid


# JWT Secret - in production, use a strong secret key
SECRET_KEY = getattr(
    settings,
    "SECRET_KEY",
    "your-secret-key-change-this-in-production-make-it-long-and-random",
)

# Bearer transport (Authorization: Bearer <token>)
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET_KEY, lifetime_seconds=3600 * 24)


# Authentication backend
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

# Current user dependencies
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Optional current user (returns None if not authenticated)
optional_current_user = fastapi_users.current_user(optional=True)
