"""Feedback DTOs — camelCase field names matching API spec."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    """Submit user feedback (supports anonymous)."""

    content: str = Field(..., min_length=1, max_length=2000, description="反馈内容")
    contact: Optional[str] = Field(default=None, description="联系方式（邮箱/手机号）")
