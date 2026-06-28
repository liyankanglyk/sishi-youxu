"""管理后台认证端点 —— Phase 1 实现。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from src.apps.admin.schemas.v1.admin import (
    AdminChangePasswordRequest,
    AdminLoginRequest,
    AdminLogoutRequest,
    AdminRefreshRequest,
)
from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


def _service(db: DbSession) -> AdminService:
    return AdminService(db)


def _set_request_meta(svc: AdminService, request: Request) -> None:
    svc._request_ip = request.client.host if request.client else None
    svc._request_ua = request.headers.get("User-Agent") or None


@router.post("/tokens", summary="管理员登录")
async def admin_login(body: AdminLoginRequest, db: DbSession, request: Request) -> dict:
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.login(
        username=body.username,
        password=body.password,
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


@router.post("/password", summary="修改管理员密码")
async def admin_change_password(
    body: AdminChangePasswordRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db)
    _set_request_meta(svc, request)
    result = await svc.change_password(admin["uuid"], body.oldPassword, body.newPassword)
    await db.commit()
    return ok(result)
