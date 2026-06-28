"""用户端 API 包 —— 暴露聚合后的 v1 路由。"""
from src.apps.user.api.v1 import api_router

__all__ = ["api_router"]