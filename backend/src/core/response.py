"""统一响应外壳，遵循 docs/03-技术架构/API接口文档.md。

成功：{ "success": true, "data": ... }
失败：{ "success": false, "error": { "code": "...", "message": "...", "detail": {} } }
"""
from typing import Any

from pydantic import BaseModel, Field


class Meta(BaseModel):
    """列表端点嵌入 `data` 内的分页元数据。"""

    total: int = 0
    page: int = 1
    page_size: int = 20
    has_more: bool = False


class SuccessResponse(BaseModel):
    success: bool = True
    data: Any = None


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorBody


def ok(data: Any = None) -> dict[str, Any]:
    """将载荷包装为成功响应。"""
    return {"success": True, "data": data}


def fail(code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """将错误包装为规范定义的失败响应外壳。"""
    return {
        "success": False,
        "error": {"code": code, "message": message, "detail": detail or {}},
    }