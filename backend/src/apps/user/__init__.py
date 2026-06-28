"""用户端 app 包。"""
from src.apps.user.api import api_router as user_router

__all__ = ["user_router"]