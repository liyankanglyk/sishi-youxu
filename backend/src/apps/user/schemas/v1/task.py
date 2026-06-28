"""任务相关 DTO —— 字段采用驼峰命名以匹配 API 规范。

所有请求/响应模型都使用驼峰命名，与 API 文档及 service 层期望的
JSON 负载保持一致。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 请求 DTO
# =============================================================================


class TaskCreateRequest(BaseModel):
    """在四象限画布中创建新任务。"""

    title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    urgencyLevel: int = Field(default=0, ge=-4, le=4, description="紧急度 -4..4 (正数=紧急)")
    importanceLevel: int = Field(default=0, ge=-4, le=4, description="重要度 -4..4 (正数=重要)")
    dueDate: Optional[date] = Field(default=None, description="截止日期 YYYY-MM-DD")
    recurrence: Optional[str] = Field(default=None, description="重复规则 RRULE 格式")
    note: Optional[str] = Field(default=None, description="备注 Markdown")
    tags: list[str] = Field(default_factory=list, description="标签 UUID 列表")
    remindAt: Optional[str] = Field(default=None, description="首次提醒时间 ISO 8601")
    remindOffsetMinutes: Optional[int] = Field(default=None, description="提前提醒分钟数")
    sortOrder: int = Field(default=0, description="排序值")


class TaskUpdateRequest(BaseModel):
    """任务的部分更新，所有字段均为可选。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200, description="任务标题")
    urgencyLevel: Optional[int] = Field(default=None, ge=-4, le=4, description="紧急度")
    importanceLevel: Optional[int] = Field(default=None, ge=-4, le=4, description="重要度")
    dueDate: Optional[date] = Field(default=None, description="截止日期")
    recurrence: Optional[str] = Field(default=None, description="重复规则")
    note: Optional[str] = Field(default=None, description="备注")
    tags: Optional[list[str]] = Field(default=None, description="标签 UUID 列表")
    remindAt: Optional[str] = Field(default=None, description="首次提醒时间")
    remindOffsetMinutes: Optional[int] = Field(default=None, description="提前提醒分钟数")
    completed: Optional[bool] = Field(default=None, description="完成状态")
    completedAt: Optional[str] = Field(default=None, description="完成时间 ISO 8601")
    sortOrder: Optional[int] = Field(default=None, description="排序值")


BatchActionLiteral = Literal["delete", "restore", "move", "complete"]


class BatchActionRequest(BaseModel):
    """对多个任务执行批量操作，支持幂等。"""

    action: BatchActionLiteral = Field(..., description="操作类型：delete / restore / move / complete")
    taskUuids: list[str] = Field(..., min_length=1, max_length=200, description="任务 UUID 列表")
    idempotencyKey: str = Field(..., min_length=1, max_length=64, description="幂等键 UUID")
    quadrant: Optional[int] = Field(default=None, ge=1, le=4, description="目标象限 action=move 时必填")


# =============================================================================
# 检查项 DTO
# =============================================================================


class ChecklistCreateRequest(BaseModel):
    """为任务添加检查项。"""

    title: str = Field(..., min_length=1, max_length=255, description="检查项标题")
    completed: bool = Field(default=False, description="完成状态")
    sortOrder: int = Field(default=0, description="排序值")


class ChecklistUpdateRequest(BaseModel):
    """检查项的部分更新。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=255, description="检查项标题")
    completed: Optional[bool] = Field(default=None, description="完成状态")
    sortOrder: Optional[int] = Field(default=None, description="排序值")


# =============================================================================
# 响应 DTO（保留以支持类型化响应模式，目前路由仍使用 dict）
# =============================================================================


class TaskOut(BaseModel):
    uuid: str
    user_uuid: str
    title: str
    urgency_level: int
    importance_level: int
    due_date: date | None = None
    recurrence: str | None = None
    note: str | None = None
    completed: bool = False
    completed_at: datetime | None = None
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime


class TaskListResponse(BaseModel):
    items: list[TaskOut] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class BatchActionResponse(BaseModel):
    affected: int = 0
    succeeded: list[str] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)


class ChecklistItemOut(BaseModel):
    uuid: str
    task_uuid: str
    title: str
    completed: bool = False
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime
