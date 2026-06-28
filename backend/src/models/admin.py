"""Admin/supporting model skeletons: audit log, login log, config, etc.

设计要点：

- `Notification.kind` 枚举新增 `wechat_subscribe` —— 用于微信小程序
  订阅消息触发记录（实际推送由前端 `wx.requestSubscribeMessage` + 后端
  `subscribeMessage.send` 配合，DB 这里只记）
- `Announcement.type` 改用 Enum 约束（之前是 String 自由文本）
- `AdminPermission` 仅保留 (role, permission) 联合主键，去掉冗余 uuid
- append-only 表（audit_log / login_log）只有 created_at，符合审计规约
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


def _utcnow() -> datetime:
    return datetime.utcnow()


class AuditLog(Base, UUIDMixin):
    __tablename__ = "sishiyouxu_audit_log"
    __table_args__ = (
        Index("idx_user_action", "user_uuid", "action"),
        Index("idx_resource", "resource_type", "resource_uuid"),
        Index("idx_created_at", "created_at"),
    )

    user_uuid: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_uuid: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, comment="操作时间"
    )


class LoginStatus(str, enum.Enum):
    success = "success"
    failed = "failed"


class LoginLog(Base, UUIDMixin):
    __tablename__ = "sishiyouxu_login_log"
    __table_args__ = (
        Index("idx_user_login", "user_uuid", "login_status"),
        Index("idx_created_at", "created_at"),
    )

    user_uuid: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    login_status: Mapped[LoginStatus] = mapped_column(
        Enum(LoginStatus, native_enum=False, length=16), nullable=False
    )
    fail_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, comment="登录时间"
    )


class SystemConfig(Base, TimestampMixin):
    __tablename__ = "sishiyouxu_system_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SensitiveWord(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_sensitive_word"
    __table_args__ = (
        Index("idx_word", "word"),
    )

    word: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AnnouncementType(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class Announcement(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_announcement"
    __table_args__ = (
        Index("idx_active_time", "is_active", "start_time", "end_time"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[AnnouncementType] = mapped_column(
        Enum(AnnouncementType, native_enum=False, length=16),
        nullable=False,
        default=AnnouncementType.info,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)


class IpBlacklist(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "sishiyouxu_ip_blacklist"
    __table_args__ = (
        Index("idx_ip", "ip_address"),
        Index("idx_expires_at", "expires_at"),
    )

    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, unique=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationKind(str, enum.Enum):
    """通知类型。

    新增 `wechat_subscribe` 用于标记「该通知对应一条微信订阅消息」，
    便于后端在调度时把 task_reminder 类的通知同时投递到 ws 通道和
    微信订阅消息通道（前端订阅过模板的情况下）。
    """

    task_reminder = "task_reminder"
    system_announcement = "system_announcement"
    wechat_subscribe = "wechat_subscribe"


class Notification(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_notification"
    __table_args__ = (
        Index("idx_user_is_read", "user_uuid", "is_read"),
        Index("idx_user_created", "user_uuid", "created_at"),
        Index("idx_task_uuid", "task_uuid"),
    )

    user_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, native_enum=False, length=32), nullable=False
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    task_uuid: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    # 微信订阅消息模板 ID（仅 kind=wechat_subscribe 时使用）
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class FeedbackStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    resolved = "resolved"


class Feedback(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_feedback"
    __table_args__ = (
        Index("idx_status", "status"),
        Index("idx_created_at", "created_at"),
    )

    user_uuid: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(
        Enum(FeedbackStatus, native_enum=False, length=16),
        nullable=False,
        default=FeedbackStatus.pending,
    )
    handled_by: Mapped[str | None] = mapped_column(CHAR(36), nullable=True)
    handled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AdminRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"


class AdminPermission(Base, TimestampMixin):
    __tablename__ = "sishiyouxu_admin_permission"
    __table_args__ = (
        UniqueConstraint("role", "permission", name="uk_role_permission"),
    )

    role: Mapped[AdminRole] = mapped_column(
        Enum(AdminRole, native_enum=False, length=20), primary_key=True
    )
    permission: Mapped[str] = mapped_column(String(100), primary_key=True)
