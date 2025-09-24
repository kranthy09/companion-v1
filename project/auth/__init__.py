"""
companion/project/auth/__init__.py
Auth App, imports auth_router
"""

# Import the auth router
from .views import auth_router

# Export for easy import
__all__ = ["auth_router"]
