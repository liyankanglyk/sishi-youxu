"""Schemas 包 —— 重新导出常用的 Pydantic DTO。"""
from src.apps.admin.schemas.v1.admin import AdminUserOut
from src.apps.user.schemas.v1.common import PageMeta

__all__ = ["AdminUserOut", "PageMeta"]