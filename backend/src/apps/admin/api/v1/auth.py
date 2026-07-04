"""管理后台认证端点 —— Phase 1 实现。

安全加固：新增图形验证码端点（get/verify）。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request

from src.apps.admin.schemas.v1.admin import (
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLogoutRequest,
    AdminRefreshRequest,
)
from src.apps.admin.services.admin_service import AdminService
from src.apps.user.schemas.v1.auth import CaptchaVerifyRequest
from src.apps.user.services.auth_service import AuthService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


# 请求体中的敏感字段 —— 记录时替换为 ***REDACTED***，避免密码/验证码落库
_SENSITIVE_KEYS = frozenset({
    "password", "oldPassword", "newPassword",
    "captchaId", "captchaSolution",
    "refresh_token", "access_token",
})


def _redact_body(body: dict[str, Any]) -> dict[str, Any]:
    """替换敏感字段后再序列化，避免密码/验证码等写到日志/数据库。"""
    if not isinstance(body, dict):
        return {"value": str(body)}
    redacted = {}
    for k, v in body.items():
        if k in _SENSITIVE_KEYS:
            redacted[k] = "***REDACTED***"
        elif isinstance(v, (dict, list)):
            redacted[k] = _redact_body(v) if isinstance(v, dict) else v
        else:
            redacted[k] = v
    return redacted


async def _safe_request_body(request: Request) -> str | None:
    """读取并脱敏请求体，限制最大长度避免膨胀。"""
    try:
        raw = await request.body()
        if not raw:
            return None
        try:
            body = json.loads(raw)
        except Exception:
            return f"<non-json: {raw[:200].decode('utf-8', errors='replace')}>"
        return json.dumps(_redact_body(body), ensure_ascii=False)
    except Exception:
        return None


def _service(db: DbSession) -> AdminService:
    return AdminService(db)


def _set_request_meta(svc: AdminService, request: Request, request_body: str | None = None) -> None:
    svc._request_ip = request.client.host if request.client else None
    svc._request_ua = request.headers.get("User-Agent") or None
    svc._request_method = request.method
    svc._request_path = request.url.path
    svc._request_body = request_body


@router.post("/tokens", summary="管理员登录")
async def admin_login(body: AdminLoginRequest, db: DbSession, request: Request) -> dict:
    svc = _service(db)
    masked_body = await _safe_request_body(request)
    _set_request_meta(svc, request, masked_body)
    result = await svc.login(
        username=body.username,
        password=body.password,
        captcha_id=body.captchaId,
        captcha_solution=body.captchaSolution,
        request_body=masked_body,
    )
    await db.commit()
    return ok(result)


@router.post("/tokens/refresh", summary="刷新管理员 Token")
async def admin_refresh(body: AdminRefreshRequest, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.refresh(body.refresh_token)
    await db.commit()
    return ok(result)


@router.delete("/tokens", summary="管理员登出")
async def admin_logout(body: AdminLogoutRequest, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.logout(body.refresh_token)
    await db.commit()
    return ok(result)


# =============================================================================
# 图形验证码（管理端独立端点，复用 AuthService 的生成/校验逻辑）
# =============================================================================


@router.get("/captcha", summary="获取图形验证码", description="返回 base64 编码的 SVG 验证码图片和 ID")
async def admin_get_captcha(db: DbSession) -> dict:
    """获取管理端图形验证码。"""
    svc = AuthService(db)
    result = await svc.generate_captcha()
    return ok(result)


@router.post("/captcha/verify", summary="校验图形验证码", description="校验用户输入的图形验证码是否正确（一次性消费）")
async def admin_verify_captcha(body: CaptchaVerifyRequest, db: DbSession) -> dict:
    """校验管理端图形验证码。"""
    svc = AuthService(db)
    verified = await svc.verify_captcha(body.captchaId, body.captchaSolution)
    return ok({"verified": verified})


@router.post("/password", summary="修改管理员密码")
async def admin_change_password(
    body: AdminChangePasswordRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.change_password(admin["uuid"], body.oldPassword, body.newPassword)
    await db.commit()
    return ok(result)
