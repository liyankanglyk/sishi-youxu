"""用户注册与个人资料端点 —— Phase 3 实现。

已实现的功能：
- POST /users — 注册 + 自动登录
- GET /users/me — 当前用户资料
- PATCH /users/me — 更新个人资料
- POST /users/me/password — 修改密码
- POST /users/me/avatar — 上传头像
- 第三方登录绑定 CRUD（token、列表、绑定、解绑）
- 提醒渠道（骨架占位）
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Form, Request, UploadFile

from src.apps.user.schemas.v1.auth import (
    BindProviderRequest,
    ChangePasswordRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UpdateReminderChannelsRequest,
)
from src.apps.user.services.auth_service import AuthService
from src.apps.user.services.user_service import UserService
from src.core.deps import DbSession, RequiredUser
from src.core.response import ok

router = APIRouter(prefix="/users", tags=["user-users"])


# =============================================================================
# 注册
# =============================================================================

@router.post("", summary="注册新用户", description="注册后自动登录并签发 JWT")
async def register(body: RegisterRequest, db: DbSession, request: Request) -> dict:
    """注册并自动登录（sign-up + sign-in 合并为单次调用）。"""
    svc = AuthService(db)
    svc._request_ip = request.client.host if request.client else None
    svc._request_ua = request.headers.get("User-Agent") or None
    result = await svc.register(body.nickname, body.provider, body.payload or {})
    await db.commit()
    return ok(result)


# =============================================================================
# 个人资料
# =============================================================================

@router.get("/me", summary="当前用户信息", description="返回已登录用户的个人信息")
async def get_me(current: RequiredUser, db: DbSession) -> dict:
    """当前登录用户信息（强制鉴权）。"""
    svc = UserService(db)
    result = await svc.get_me(current["uuid"])
    return ok(result)


@router.patch("/me", summary="更新个人资料", description="更新昵称、语言偏好等")
async def update_me(body: UpdateProfileRequest, current: RequiredUser, db: DbSession) -> dict:
    """更新当前用户的个人资料。"""
    svc = UserService(db)
    update_data = body.model_dump(exclude_unset=True)
    result = await svc.update_me(current["uuid"], update_data)
    await db.commit()
    return ok(result)


# =============================================================================
# 密码
# =============================================================================

@router.post("/me/password", summary="修改密码", description="验证旧密码后设置新密码，并强制登出所有设备")
async def change_password(body: ChangePasswordRequest, current: RequiredUser, db: DbSession) -> dict:
    """修改密码；成功后所有设备强制下线。"""
    svc = UserService(db)
    result = await svc.change_password(current["uuid"], body.oldPassword, body.newPassword)
    await db.commit()
    return ok(result)


# =============================================================================
# 头像
# =============================================================================

@router.post("/me/avatar", summary="上传头像", description="上传头像图片（JPG/PNG/WebP，最大 2MB）")
async def upload_avatar(
    current: RequiredUser,
    db: DbSession,
    file: UploadFile = File(..., description="头像图片文件"),
) -> dict:
    """上传并更新用户头像。"""
    svc = UserService(db)
    content = await file.read()
    filename = file.filename or "avatar.jpg"
    result = await svc.upload_avatar(current["uuid"], content, filename)
    await db.commit()
    return ok(result)


# =============================================================================
# 第三方登录绑定
# =============================================================================

@router.post("/me/auth-linkage/token", summary="生成绑定 Token", description="获取用于绑定新登录方式的临时令牌")
async def create_link_token(current: RequiredUser, db: DbSession) -> dict:
    """获取绑定临时令牌（5 分钟有效）。"""
    svc = UserService(db)
    result = await svc.create_link_token(current["uuid"])
    return ok(result)


@router.get("/me/auth-linkage", summary="查询已绑定登录方式", description="列出当前账号已绑定的所有登录方式")
async def list_linkage(current: RequiredUser, db: DbSession) -> dict:
    """列出已绑定的登录方式（标识脱敏显示）。"""
    svc = UserService(db)
    result = await svc.list_linkage(current["uuid"])
    return ok(result)


@router.put("/me/auth-linkage/{provider}", summary="绑定新登录方式", description="为当前账号绑定新的登录方式（phone_sms / email_code）")
async def bind_provider(
    provider: str,
    body: BindProviderRequest,
    current: RequiredUser,
    db: DbSession,
) -> dict:
    """绑定新的登录方式到当前账号。"""
    svc = UserService(db)
    result = await svc.bind_provider(
        current["uuid"], provider, body.linkToken, body.payload or {}
    )
    await db.commit()
    return ok(result)


@router.delete("/me/auth-linkage/{provider}", summary="解绑登录方式", description="解绑指定的登录方式")
async def unbind_provider(provider: str, current: RequiredUser, db: DbSession) -> dict:
    """解绑登录方式（至少保留一种）。"""
    svc = UserService(db)
    await svc.unbind_provider(current["uuid"], provider)
    await db.commit()
    return ok(None)


# =============================================================================
# 提醒渠道（骨架）
# =============================================================================

@router.get("/me/reminder-channels", summary="获取提醒渠道设置")
async def get_reminder_channels(current: RequiredUser) -> dict:
    """获取已开启的提醒渠道（骨架占位）。"""
    # Phase 4+ 将从 Redis 或独立表中读取
    return ok({
        "channels": [
            {"type": "web_push", "enabled": True, "label": "浏览器推送"},
            {"type": "wechat_subscribe", "enabled": False, "label": "微信订阅消息"},
        ],
    })


@router.patch("/me/reminder-channels", summary="更新提醒渠道设置")
async def update_reminder_channels(
    current: RequiredUser, body: UpdateReminderChannelsRequest
) -> dict:
    """更新提醒渠道设置（骨架占位）。"""
    return ok({
        "message": "reminder channels updated (skeleton)",
        "channels": [c.model_dump() for c in body.channels],
    })
