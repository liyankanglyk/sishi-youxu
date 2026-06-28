"""标签相关 DTO —— 字段采用驼峰命名以匹配 API 规范。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# 请求 DTO
# =============================================================================


class TagCreateRequest(BaseModel):
    """创建自定义标签。"""

    name: str = Field(..., min_length=1, max_length=50, description="标签名称")
    color: str = Field(
        ...,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="颜色 HEX 格式，如 #A78BFA",
    )


class TagUpdateRequest(BaseModel):
    """标签的部分更新，预设标签不可修改。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50, description="标签名称")
    color: Optional[str] = Field(
        default=None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="颜色 HEX 格式，如 #A78BFA",
    )


# =============================================================================
# 响应 DTO
# =============================================================================


class TagOut(BaseModel):
    uuid: str
    user_uuid: str
    name: str
    color: str
    is_preset: bool = False
    created_at: datetime
    updated_at: datetime
