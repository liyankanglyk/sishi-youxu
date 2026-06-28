"""自定义异常体系。

骨架定义了项目中统一使用的异常形态：
  - BusinessException —— 映射为包含 `code` + `message` 的 JSON 错误体。
  - NotFoundException —— 用于 404 资源的便捷类。
"""
from typing import Any


class BusinessException(Exception):
    """任意应用级错误的基类。

    `code` 遵循规范的命名约定（如 AUTH_INVALID_CREDENTIALS）。
    `http_status` 控制全局处理器输出的 HTTP 状态码。
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