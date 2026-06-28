"""v1 管理后台 schemas 聚合器。"""

from src.apps.admin.schemas.v1.admin import (
    AdminConfigUpdateRequest,
    AdminFeedbackUpdateRequest,
    AdminLoginRequest,
    AdminLogoutRequest,
    AdminRefreshRequest,
    AdminUserBatchRequest,
    AdminUserOut,
    AdminUserUpdateRequest,
)

__all__ = [
    "AdminConfigUpdateRequest",
    "AdminFeedbackUpdateRequest",
    "AdminLoginRequest",
    "AdminLogoutRequest",
    "AdminRefreshRequest",
    "AdminUserBatchRequest",
    "AdminUserOut",
    "AdminUserUpdateRequest",
]
