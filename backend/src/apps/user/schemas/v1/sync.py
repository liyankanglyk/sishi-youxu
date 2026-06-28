"""Sync DTOs — camelCase field names matching API spec."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SyncOpItem(BaseModel):
    """A single sync operation."""

    opId: str = Field(..., min_length=1, description="客户端生成的幂等 ID")
    entity: str = Field(..., description="实体类型：task / tag / taskTag / checklistItems")
    action: str = Field(..., description="操作类型：upsert / delete")
    payload: dict = Field(..., description="完整实体记录")
    clientTs: Optional[int] = Field(default=None, description="客户端操作时间戳（毫秒）")


class SyncPushRequest(BaseModel):
    """Batch push local ops to server."""

    ops: list[SyncOpItem] = Field(..., min_length=1, max_length=100, description="操作列表")
