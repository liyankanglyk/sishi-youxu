"""管理后台内容管理 DTO —— 字段名采用 camelCase 以匹配 API 规范。"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AdminTaskCreateRequest(BaseModel):
    """管理员创建任务请求。"""

    title: str = Field(..., min_length=1, max_length=200, description="任务标题")
    userUuid: str = Field(..., description="任务所属用户 UUID")
    urgencyLevel: int = Field(default=0, ge=-4, le=4, description="紧急度 -4..4 (正数=紧急)")
    importanceLevel: int = Field(default=0, ge=-4, le=4, description="重要度 -4..4 (正数=重要)")
    dueDate: Optional[str] = Field(default=None, description="截止日期 (YYYY-MM-DD)")
    note: Optional[str] = Field(default=None, description="备注")
    tagUuids: Optional[list[str]] = Field(default=None, description="标签 UUID 列表")


class AdminTaskUpdateRequest(BaseModel):
    """管理员更新任务请求。"""

    title: Optional[str] = Field(default=None, min_length=1, max_length=200, description="任务标题")
    urgencyLevel: Optional[int] = Field(default=None, ge=-4, le=4, description="紧急度")
    importanceLevel: Optional[int] = Field(default=None, ge=-4, le=4, description="重要度")
    dueDate: Optional[str] = Field(default=None, description="截止日期 (YYYY-MM-DD)")
    note: Optional[str] = Field(default=None, description="备注")
    completed: Optional[bool] = Field(default=None, description="是否完成")
    tagUuids: Optional[list[str]] = Field(default=None, description="标签 UUID 列表")


class AdminTaskBatchRequest(BaseModel):
    """批量操作任务请求。"""

    action: Literal["delete", "restore"] = Field(..., description="操作类型：delete / restore")
    taskUuids: list[str] = Field(..., min_length=1, max_length=200, description="任务 UUID 列表")


class AdminTagCreateRequest(BaseModel):
    """管理员创建标签请求。"""

    name: str = Field(..., min_length=1, max_length=50, description="标签名称")
    color: str = Field(default="#6366f1", description="标签颜色 HEX 格式")
    userUuid: Optional[str] = Field(default=None, description="所属用户 UUID（为空则创建为系统预设标签）")


class AdminTagUpdateRequest(BaseModel):
    """更新标签请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50, description="标签名称")
    color: Optional[str] = Field(default=None, description="标签颜色 HEX 格式")
