"""Custom exception hierarchy.

Skeleton defines the shape used across the project:
  - BusinessException — mapped to a JSON error body with `code` + `message`.
  - NotFoundException — convenience for 404 resources.
"""
from typing import Any


class BusinessException(Exception):
    """Base class for any application-level error.

    `code` follows the spec naming convention (e.g. AUTH_INVALID_CREDENTIALS).
    `http_status` controls the HTTP status code emitted by the global handler.
    """

    code: str = "INTERNAL_ERROR"
    http_status: int = 400
    message: str = "业务错误"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        http_status: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.detail = detail or {}
        super().__init__(self.message)


class NotFoundException(BusinessException):
    code = "NOT_FOUND"
    http_status = 404
    message = "资源不存在"


class UnauthorizedException(BusinessException):
    code = "UNAUTHORIZED"
    http_status = 401
    message = "未认证"


class ForbiddenException(BusinessException):
    code = "FORBIDDEN"
    http_status = 403
    message = "无权限"


class ConflictException(BusinessException):
    code = "CONFLICT"
    http_status = 409
    message = "资源冲突"


class RateLimitedException(BusinessException):
    code = "RATE_LIMITED"
    http_status = 429
    message = "请求过于频繁"


class ValidationException(BusinessException):
    code = "VALIDATION_ERROR"
    http_status = 400
    message = "参数校验失败"