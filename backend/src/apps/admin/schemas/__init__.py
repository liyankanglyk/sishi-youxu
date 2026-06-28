"""Schemas package — re-export common Pydantic DTOs."""
from src.apps.admin.schemas.v1.admin import AdminUserOut
from src.apps.user.schemas.v1.common import PageMeta

__all__ = ["AdminUserOut", "PageMeta"]