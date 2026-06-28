"""User authentication endpoints — Phase 3 implementation.

Implemented (all real business via AuthService):
- POST /auth/tokens — login (password / phone_sms / email_code)
- POST /auth/tokens/refresh — refresh access token (旧 token 立即撤销)
- POST /auth/tokens/logout — revoke single refresh token (幂等)
- POST /auth/tokens/logout-all — revoke all refresh tokens for current user
- POST /auth/wechat/login — WeChat mini-program code2session + JWT
- POST /auth/ws-ticket — issue one-time WS auth ticket (60s TTL, Redis)
- GET  /auth/login-methods — list enabled login providers
- GET  /auth/captcha / POST /auth/captcha/verify — SVG captcha (5min TTL)
- POST /auth/sms/send / POST /auth/sms/login — SMS code (mock, 60s 限流)
- POST /auth/email/send / POST /auth/email/login — email code (mock)
- POST /auth/password/reset-request / POST /auth/password/reset — reset password

所有 endpoint 不带 `response_model`，让 `ok()` 包络完整返回。
"""
from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.apps.user.schemas.v1.auth import (
    CaptchaVerifyRequest,
    EmailCodeLoginRequest,
    EmailCodeSendRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetRequest,
    RefreshRequest,
    SmsCodeLoginRequest,
    SmsCodeSendRequest,
    WechatLoginRequest,
)
from src.apps.user.services.auth_service import AuthService
from src.core.database import get_db as get_db_dep
from src.core.deps import DbSession, RequiredUser
from src.core.response import ok

router = APIRouter(prefix="/auth", tags=["user-auth"])


def _service(db: DbSession) -> AuthService:
    return AuthService(db)


def _set_request_meta(svc: AuthService, request: Request) -> None:
    svc._request_ip = request.client.host if request.client else None
    svc._request_ua = request.headers.get("User-Agent") or None


@router.post("/tokens", summary="账号登录", description="支持 password / phone_sms / email_code 三种方式")
async def login(body: LoginRequest, db: DbSession, request: Request) -> dict:
    """账号登录（password / phone_sms / email_code）。"""
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.login(body.provider, body.payload or {})
    await db.commit()
    return ok(result)


@router.post("/tokens/refresh", summary="刷新 Token", description="用 refresh_token 换取新的 access_token")
async def refresh_token(body: RefreshRequest, db: DbSession) -> dict:
    """刷新访问令牌；旧 refresh_token 立即失效，重复使用会触发吊销。"""
    svc = _service(db)
    result = await svc.refresh(body.refreshToken)
    await db.commit()
    return ok(result)


@router.post("/tokens/logout", summary="登出", description="撤销当前设备的 refresh_token")
async def logout(body: LogoutRequest, db: DbSession) -> dict:
    """退出登录，撤销当前 refresh_token（幂等）。"""
    svc = _service(db)
    result = await svc.logout(body.refreshToken)
    await db.commit()
    return ok(result)


@router.post("/tokens/logout-all", summary="登出所有设备", description="撤销该用户所有 refresh_token")
async def logout_all(current: RequiredUser, db: DbSession) -> dict:
    """强制登出所有设备。"""
    svc = _service(db)
    result = await svc.logout_all(current["uuid"])
    await db.commit()
    return ok(result)


@router.post("/wechat/login", summary="微信登录", description="小程序 wx.login() code 换取 JWT")
async def wechat_login(body: WechatLoginRequest, db: DbSession, request: Request) -> dict:
    """微信小程序登录 —— 已接入真实 AuthService。"""
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.wechat_login(
        body.code,
        encrypted_data=body.encrypted_data,
        iv=body.iv,
        invite_code=body.invite_code,
    )
    await db.commit()
    return ok(result)


@router.post("/ws-ticket", summary="获取 WebSocket Ticket", description="access_token 换一次性 ws ticket")
async def issue_ws_ticket(current: RequiredUser, db: DbSession) -> dict:
    """获取 WebSocket 一次性 ticket（需有效 access_token）。"""
    svc = _service(db)
    result = await svc.issue_ws_ticket(current["uuid"])
    return ok(result)


# ---------------------------------------------------------------------------
# 真实业务
# ---------------------------------------------------------------------------
@router.get("/login-methods", summary="获取可用登录方式", description="返回当前系统支持的登录方式列表")
async def login_methods(db: DbSession) -> dict:
    """返回当前可用的登录方式列表。"""
    svc = _service(db)
    result = await svc.list_login_methods()
    return ok(result)


@router.get("/captcha", summary="获取图形验证码", description="返回 Base64 编码的验证码图片和 ID")
async def get_captcha(db: DbSession) -> dict:
    """获取图形验证码。"""
    svc = _service(db)
    result = await svc.generate_captcha()
    return ok(result)


@router.post("/captcha/verify", summary="校验图形验证码", description="校验用户输入的图形验证码是否正确")
async def verify_captcha(body: CaptchaVerifyRequest, db: DbSession) -> dict:
    """校验图形验证码（一次性消费）。"""
    svc = _service(db)
    verified = await svc.verify_captcha(body.captchaId, body.captchaSolution)
    return ok({"verified": verified})


@router.post("/sms/send", summary="发送短信验证码", description="向指定手机号发送短信验证码")
async def send_sms(body: SmsCodeSendRequest, db: DbSession) -> dict:
    """发送短信验证码（mock 模式：写 Redis + 日志）。"""
    svc = _service(db)
    result = await svc.send_sms_code(
        body.phone,
        body.purpose,
        captcha_id=body.captchaId,
        captcha_solution=body.captchaSolution,
    )
    return ok(result)


@router.post("/sms/login", summary="短信登录", description="手机号 + 短信验证码登录")
async def login_by_sms(body: SmsCodeLoginRequest, db: DbSession, request: Request) -> dict:
    """手机号 + 短信验证码登录。"""
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.login("phone_sms", {"phone": body.phone, "code": body.code})
    await db.commit()
    return ok(result)


@router.post("/email/send", summary="发送邮箱验证码", description="向指定邮箱发送验证码邮件")
async def send_email_code(body: EmailCodeSendRequest, db: DbSession) -> dict:
    """发送邮箱验证码（mock 模式：写 Redis + 日志）。"""
    svc = _service(db)
    result = await svc.send_email_code(body.email, body.purpose)
    return ok(result)


@router.post("/email/login", summary="邮箱验证码登录", description="邮箱 + 验证码登录")
async def login_by_email(body: EmailCodeLoginRequest, db: DbSession, request: Request) -> dict:
    """邮箱 + 邮箱验证码登录。"""
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.login("email_code", {"email": body.email, "code": body.code})
    await db.commit()
    return ok(result)


@router.post("/password/reset-request", summary="请求密码重置", description="向邮箱发送密码重置链接")
async def password_reset_request(
    db: DbSession,
    email: str = Query(..., description="注册邮箱"),
) -> dict:
    """请求密码重置（mock：无论邮箱是否存在都返回成功）。"""
    svc = _service(db)
    result = await svc.request_password_reset(email)
    return ok(result)


@router.post("/password/reset", summary="执行密码重置", description="使用邮件中的重置令牌设置新密码")
async def password_reset(body: PasswordResetRequest, db: DbSession) -> dict:
    """使用 reset_token 设置新密码；成功后所有 refresh_token 失效。"""
    svc = _service(db)
    result = await svc.do_password_reset(body.resetToken, body.newPassword)
    await db.commit()
    return ok(result)