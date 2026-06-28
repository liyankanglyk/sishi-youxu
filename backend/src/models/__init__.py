"""模型注册中心 —— 导入本包即可将所有表注册到 Base.metadata。"""
from src.models.admin import (
    AdminPermission,
    AdminRole,
    Announcement,
    AnnouncementType,
    AuditLog,
    Feedback,
    FeedbackStatus,
    IpBlacklist,
    LoginLog,
    LoginStatus,
    Notification,
    NotificationKind,
    SensitiveWord,
    SystemConfig,
)
from src.models.auth import AuthIdentity, AuthProvider, RefreshToken
from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from src.models.task import (
    ReminderState,
    Tag,
    Task,
    TaskChecklist,
    TaskTag,
)
from src.models.user import User, UserRole, UserStatus

__all__ = [
    # base
    "Base",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDMixin",
    # user
    "User",
    "UserRole",
    "UserStatus",
    # auth
    "AuthIdentity",
    "AuthProvider",
    "RefreshToken",
    # task
    "Task",
    "Tag",
    "TaskTag",
    "TaskChecklist",
    "ReminderState",
    # admin/supporting
    "AdminPermission",
    "AdminRole",
    "Announcement",
    "AnnouncementType",
    "AuditLog",
    "Feedback",
    "FeedbackStatus",
    "IpBlacklist",
    "LoginLog",
    "LoginStatus",
    "Notification",
    "NotificationKind",
    "SensitiveWord",
    "SystemConfig",
]
