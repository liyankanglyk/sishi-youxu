"""同步相关 DTO —— 字段采用驼峰命名以匹配 API 规范。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SyncOpItem(BaseModel):
    """单个同步操作。"""

    opId: str = Field(..., min_length=1, description="客户端生成的幂等 ID")
    entity: str = Field(..., description="实体类型：task / tag / taskTag / checklistItems")
    action: str = Field(..., description="操作类型：upsert / delete")
    payload: dict = Field(..., description="完整实体记录")
    clientTs: Optional[int] = Field(default=None, description="客户端操作时间戳（毫秒）")


class SyncPushRequest(BaseModel):
    """批量推送本地操作到服务端。"""

    ops: list[SyncOpItem] = Field(..., min_length=1, max_length=100, description="操作列表")
