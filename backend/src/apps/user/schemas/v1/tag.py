"""Tag DTOs — camelCase field names matching API spec."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
# Request DTOs
# =============================================================================


class TagCreateRequest(BaseModel):
    """Create a custom tag."""

    name: str = Field(..., min_length=1, max_length=50, description="标签名称")
    color: str = Field(
        ...,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="颜色 HEX 格式，如 #A78BFA",
    )


class TagUpdateRequest(BaseModel):
    """Partial update for a tag. Preset tags cannot be modified."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50, description="标签名称")
    color: Optional[str] = Field(
        default=None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="颜色 HEX 格式，如 #A78BFA",
    )


# =============================================================================
# Response DTOs
# =============================================================================


class TagOut(BaseModel):
    uuid: str
    user_uuid: str
    name: str
    color: str
    is_preset: bool = False
    created_at: datetime
    updated_at: datetime
