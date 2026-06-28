"""用户模型骨架 —— 仅含字段，暂无关联关系。"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    super_admin = "super_admin"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"
    banned = "banned"
    deleted = "deleted"


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_user"

    nickname: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        nullable=False,
        default=UserRole.user,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=20),
        nullable=False,
        default=UserStatus.active,
    )
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="zh-CN")