"""SQLAlchemy 2.0 声明式基类 + 可复用 mixin。

骨架提供：
  - UUIDMixin：CHAR(36) 主键，自动填充 uuid4
  - TimestampMixin：created_at / updated_at（UTC）
  - SoftDeleteMixin：deleted_at 列（NULL = 存活）
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    # 朴素 UTC —— 与 MySQL DATETIME 列匹配（不含时区信息）。
    # 所有业务代码均使用朴素 datetime 进行比较与运算。
    return datetime.utcnow()


class Base(DeclarativeBase):
    """声明式基类。所有 ORM 模型均继承自此。"""


class UUIDMixin:
    """主键：CHAR(36) UUID4。"""

    uuid: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="主键 UUID",
    )


class TimestampMixin:
    """created_at / updated_at 列，自动维护。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
        comment="更新时间",
    )


class SoftDeleteMixin:
    """软删除列。NULL 表示存活。"""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        comment="软删除时间",
    )


__all__ = ["Base", "UUIDMixin", "TimestampMixin", "SoftDeleteMixin"]