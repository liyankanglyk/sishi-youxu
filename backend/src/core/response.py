"""Unified response envelope per docs/03-技术架构/API接口文档.md.

Success: { "success": true, "data": ... }
Failure: { "success": false, "error": { "code": "...", "message": "...", "detail": {} } }
"""
from typing import Any

from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Pagination metadata embedded inside `data` for list endpoints."""

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
    """Wrap a payload as a success response."""
    return {"success": True, "data": data}


def fail(code: str, message: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """Wrap an error as the spec'd failure envelope."""
    return {
        "success": False,
        "error": {"code": code, "message": message, "detail": detail or {}},
    }