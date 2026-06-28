"""SQLAlchemy 2.0 declarative base + reusable mixins.

Skeleton provides:
  - UUIDMixin: CHAR(36) primary key, auto-filled with uuid4
  - TimestampMixin: created_at / updated_at (UTC)
  - SoftDeleteMixin: deleted_at column (NULL = alive)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    # Naive UTC — matches MySQL DATETIME column (no tz info).
    # All business code compares/arithmetics naive datetimes.
    return datetime.utcnow()


class Base(DeclarativeBase):
    """Declarative base. All ORM models inherit from this."""


class UUIDMixin:
    """Primary key: CHAR(36) UUID4."""

    uuid: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="主键 UUID",
    )


class TimestampMixin:
    """created_at / updated_at columns, auto-managed."""

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
    """Soft delete column. NULL means alive."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        default=None,
        comment="软删除时间",
    )


__all__ = ["Base", "UUIDMixin", "TimestampMixin", "SoftDeleteMixin"]