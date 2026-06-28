"""Admin user-management endpoints — Phase 1 implementation."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from src.apps.admin.schemas.v1.admin import (
    AdminResetUserPasswordRequest,
    AdminUserBatchRequest,
    AdminUserUpdateRequest,
)
from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _service(db: DbSession, request: Request | None = None) -> AdminService:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    return svc


@router.get("", summary="用户列表")
async def admin_list_users(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    startTime: str | None = Query(default=None, alias="startTime"),
    endTime: str | None = Query(default=None, alias="endTime"),
) -> dict:
    svc = _service(db)
    result = await svc.list_users(page=page, page_size=pageSize, keyword=keyword,
                                   status=status, role=role, start_time=startTime, end_time=endTime)
    return ok(result)


@router.get("/{uuid}", summary="用户详情")
async def admin_get_user(uuid: str, db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_user(uuid)
    return ok(result)


@router.patch("/{uuid}", summary="更新用户")
async def admin_update_user(
    uuid: str, body: AdminUserUpdateRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.update_user(uuid, body.model_dump(), admin_uuid=admin["uuid"])
    await db.commit()
    return ok(result)


@router.delete("/{uuid}", summary="删除用户（软删除）")
async def admin_delete_user(uuid: str, db: DbSession, admin: RequireAdmin, request: Request) -> dict:
    svc = _service(db, request)
    await svc.delete_user(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(None)


@router.post("/{uuid}/disable", summary="禁用用户")
async def admin_disable_user(uuid: str, db: DbSession, admin: RequireAdmin, request: Request) -> dict:
    svc = _service(db, request)
    result = await svc.disable_user(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(result)


@router.post("/{uuid}/enable", summary="启用用户")
async def admin_enable_user(uuid: str, db: DbSession, admin: RequireAdmin, request: Request) -> dict:
    svc = _service(db, request)
    result = await svc.enable_user(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(result)


@router.post("/{uuid}/force-logout", summary="强制登出")
async def admin_force_logout(uuid: str, db: DbSession, admin: RequireAdmin, request: Request) -> dict:
    svc = _service(db, request)
    result = await svc.force_logout(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(result)


@router.post("/{uuid}/reset-password", summary="重置用户密码")
async def admin_reset_user_password(
    uuid: str, body: AdminResetUserPasswordRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.reset_user_password(uuid, body.newPassword, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(result)


@router.post("/batch", summary="批量操作")
async def admin_batch_users(
    body: AdminUserBatchRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.batch_users(
        action=body.action,
        uuids=body.uuids,
        admin_uuid=admin["uuid"],
    )
    await db.commit()
    return ok(result)


@router.get("/export", summary="导出用户 CSV")
async def admin_export_users(db: DbSession, _admin: RequireAdmin) -> Response:
    svc = _service(db)
    csv_data = await svc.export_users()
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


# ── Me endpoint ──
me_router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@me_router.get("/me", summary="当前管理员信息")
async def admin_get_me(admin: RequireAdmin) -> dict:
    return ok(admin)
