"""User app package."""
from src.apps.user.api import api_router as user_router

__all__ = ["user_router"]