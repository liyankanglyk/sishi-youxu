"""Admin audit-log endpoints — Phase 1 implementation.

Login logs skeleton replaced with real implementation in Phase 4.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


def _service(db: DbSession) -> AdminService:
    return AdminService(db)


@router.get("", summary="审计日志列表")
async def list_audit(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    userUuid: str | None = Query(default=None, alias="userUuid"),
    action: str | None = Query(default=None),
    resourceType: str | None = Query(default=None, alias="resourceType"),
    startTime: str | None = Query(default=None, alias="startTime"),
    endTime: str | None = Query(default=None, alias="endTime"),
) -> dict:
    svc = _service(db)
    result = await svc.list_audit(
        page=page, page_size=pageSize, user_uuid=userUuid,
        action=action, resource_type=resourceType,
        start_time=startTime, end_time=endTime,
    )
    return ok(result)


@router.get("/{uuid}", summary="审计日志详情")
async def get_audit_entry(uuid: str, db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_audit_entry(uuid)
    return ok(result)


# ── Login logs (Phase 4: real implementation) ──
login_log_router = APIRouter(prefix="/admin/login-logs", tags=["admin-audit"])


@login_log_router.get("", summary="登录日志列表")
async def list_login_logs(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    userUuid: str | None = Query(default=None, alias="userUuid"),
):
    svc = AdminService(db)
    result = await svc.list_login_logs(
        page=page, page_size=pageSize,
        status=status, provider=provider, user_uuid=userUuid,
    )
    return ok(result)
