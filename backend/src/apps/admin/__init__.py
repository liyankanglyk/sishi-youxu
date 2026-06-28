"""管理后台 app 包。"""
from src.apps.admin.api import api_router as admin_router

__all__ = ["admin_router"]