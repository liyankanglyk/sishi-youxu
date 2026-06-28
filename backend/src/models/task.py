"""Task-domain model skeletons (task, tag, task_tag, checklist).

设计要点：

- `recurrence` 存 RFC 5545 RRULE 字符串（含 EXDATE/RDATE），用 TEXT
- 提醒字段 `remind_at` + `remind_offset_minutes` + `reminder_state`
  让后端 APScheduler 能直接扫描 `idx_user_remind`
- `urgency_level` / `importance_level` 为 INT 类型，范围 -4 ~ 4，
  直接入库，用于象限分类和排序
- 软删除 + idx_user_completed 共同支撑「已删除/未删除 + 完成/未完成」复合查询
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class ReminderState(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    cancelled = "cancelled"


class Task(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_task"
    __table_args__ = (
        Index("idx_user_completed", "user_uuid", "completed"),
        Index("idx_user_due_date", "user_uuid", "due_date"),
        Index("idx_user_remind", "remind_at", "reminder_state"),
        Index("idx_updated_at", "updated_at"),
    )

    user_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    urgency_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    importance_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recurrence: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 提醒（与小程序通知打通：后端调度后通过 WebSocket / WeChat 订阅消息推）
    remind_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remind_offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_state: Mapped[ReminderState] = mapped_column(
        Enum(ReminderState, native_enum=False, length=16),
        nullable=False,
        default=ReminderState.pending,
    )


class Tag(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_tag"
    __table_args__ = (
        Index("idx_user_name", "user_uuid", "name"),
    )

    user_uuid: Mapped[str | None] = mapped_column(CHAR(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#cccccc")
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskTag(Base, TimestampMixin):
    """Many-to-many join between tasks and tags.

    Hard-deleted (no soft-delete): the composite PK (task_uuid, tag_uuid)
    must remain globally unique, and re-associating the same pair after a
    removal must succeed — both rules break under MySQL if a deleted_at
    column co-exists with the PK.
    """

    __tablename__ = "sishiyouxu_task_tag"
    __table_args__ = (
        Index("idx_tag_uuid", "tag_uuid"),
    )

    task_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, primary_key=True)
    tag_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, primary_key=True)


class TaskChecklist(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_task_checklist"
    __table_args__ = (
        Index("idx_task_sort", "task_uuid", "sort_order"),
    )

    task_uuid: Mapped[str] = mapped_column(
        CHAR(36), ForeignKey("sishiyouxu_task.uuid"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
