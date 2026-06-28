"""管理后台反馈端点 —— Phase 1 实现。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from src.apps.admin.schemas.v1.admin import AdminFeedbackUpdateRequest
from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.exceptions import NotFoundException
from src.core.response import ok
from src.models.admin import Feedback

router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])


def _service(db: DbSession, request: Request | None = None) -> AdminService:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    return svc


@router.get("", summary="反馈列表")
async def admin_list_feedback(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: str | None = Query(default=None),
) -> dict:
    svc = _service(db)
    result = await svc.list_feedback(page=page, page_size=pageSize, status=status)
    return ok(result)


@router.patch("/{uuid}", summary="更新反馈状态")
async def admin_update_feedback(
    uuid: str, body: AdminFeedbackUpdateRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.update_feedback(uuid, body.status, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(result)


@router.delete("/{uuid}", summary="删除反馈")
async def admin_delete_feedback(uuid: str, db: DbSession, _admin: RequireAdmin) -> dict:
    # 软删除
    stmt = select(Feedback).where(Feedback.uuid == uuid, Feedback.deleted_at.is_(None))
    fb = (await db.execute(stmt)).scalar_one_or_none()
    if fb is None:
        raise NotFoundException("反馈不存在", code="FEEDBACK_NOT_FOUND")
    fb.deleted_at = datetime.utcnow()
    await db.commit()
    return ok(None)
