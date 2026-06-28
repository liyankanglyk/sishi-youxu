"""反馈相关 DTO —— 字段采用驼峰命名以匹配 API 规范。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    """提交用户反馈（支持匿名）。"""

    content: str = Field(..., min_length=1, max_length=2000, description="反馈内容")
    contact: Optional[str] = Field(default=None, description="联系方式（邮箱/手机号）")
