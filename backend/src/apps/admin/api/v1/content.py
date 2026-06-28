"""Admin content management endpoints — tasks and tags.

Implemented:
- GET /admin/tasks — paginated task list with filters
- GET /admin/tasks/{uuid} — task detail with tags, checklist, user info
- DELETE /admin/tasks/{uuid} — soft-delete task
- POST /admin/tasks/batch — batch delete/restore
- GET /admin/tags — paginated tag list with filters
- GET /admin/tags/{uuid} — tag detail with task count and users
- PATCH /admin/tags/{uuid} — update tag
- DELETE /admin/tags/{uuid} — soft-delete tag
- GET /admin/users/{uuid}/tasks — user's task list
- GET /admin/users/{uuid}/tags — user's tag list
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from src.apps.admin.schemas.v1.content import (
    AdminTaskCreateRequest,
    AdminTaskUpdateRequest,
    AdminTagCreateRequest,
    AdminTagUpdateRequest,
    AdminTaskBatchRequest,
)
from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(tags=["admin-content"])


def _service(db: DbSession, request: Request | None = None) -> AdminService:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    return svc


# =============================================================================
# Task Management
# =============================================================================


@router.get("/admin/tasks", summary="任务列表（管理员）")
async def admin_list_tasks(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    userUuid: str | None = Query(default=None, alias="userUuid"),
    quadrant: int | None = Query(default=None, ge=1, le=4),
    completed: bool | None = Query(default=None),
    tagUuid: str | None = Query(default=None, alias="tagUuid"),
    startTime: str | None = Query(default=None, alias="startTime"),
    endTime: str | None = Query(default=None, alias="endTime"),
) -> dict:
    svc = _service(db)
    result = await svc.list_tasks(
        page=page, page_size=pageSize,
        user_uuid=userUuid, quadrant=quadrant,
        completed=completed, tag_uuid=tagUuid,
        start_time=startTime, end_time=endTime,
    )
    return ok(result)


@router.get("/admin/tasks/{uuid}", summary="任务详情（管理员）")
async def admin_get_task(uuid: str, db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_task(uuid)
    return ok(result)


@router.post("/admin/tasks", summary="创建任务（管理员）")
async def admin_create_task(
    body: AdminTaskCreateRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.create_task(
        admin_uuid=admin["uuid"],
        user_uuid=body.userUuid,
        title=body.title,
        urgency_level=body.urgencyLevel,
        importance_level=body.importanceLevel,
        due_date=body.dueDate,
        note=body.note,
        tag_uuids=body.tagUuids,
    )
    await db.commit()
    return ok(result)


@router.patch("/admin/tasks/{uuid}", summary="更新任务（管理员）")
async def admin_update_task(
    uuid: str,
    body: AdminTaskUpdateRequest,
    db: DbSession,
    admin: RequireAdmin,
    request: Request,
) -> dict:
    svc = _service(db, request)
    result = await svc.update_task(
        uuid=uuid,
        admin_uuid=admin["uuid"],
        title=body.title,
        urgency_level=body.urgencyLevel,
        importance_level=body.importanceLevel,
        due_date=body.dueDate,
        note=body.note,
        completed=body.completed,
        tag_uuids=body.tagUuids,
    )
    await db.commit()
    return ok(result)


@router.delete("/admin/tasks/{uuid}", summary="删除任务（管理员）")
async def admin_delete_task(uuid: str, db: DbSession, admin: RequireAdmin, request: Request) -> dict:
    svc = _service(db, request)
    await svc.delete_task(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(None)


@router.post("/admin/tasks/batch", summary="批量操作任务（管理员）")
async def admin_batch_tasks(
    body: AdminTaskBatchRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.batch_tasks(
        action=body.action,
        task_uuids=body.taskUuids,
        admin_uuid=admin["uuid"],
    )
    await db.commit()
    return ok(result)


# =============================================================================
# Tag Management
# =============================================================================


@router.post("/admin/tags", summary="创建标签（管理员）")
async def admin_create_tag(
    body: AdminTagCreateRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.create_tag(
        name=body.name,
        color=body.color,
        user_uuid=body.userUuid,
        admin_uuid=admin["uuid"],
    )
    await db.commit()
    return ok(result)


@router.get("/admin/tags", summary="标签列表（管理员）")
async def admin_list_tags(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    userUuid: str | None = Query(default=None, alias="userUuid"),
    q: str | None = Query(default=None, description="名称模糊搜索"),
) -> dict:
    svc = _service(db)
    result = await svc.list_tags(
        page=page, page_size=pageSize,
        user_uuid=userUuid, q=q,
    )
    return ok(result)


@router.get("/admin/tags/{uuid}", summary="标签详情（管理员）")
async def admin_get_tag(uuid: str, db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_tag(uuid)
    return ok(result)


@router.patch("/admin/tags/{uuid}", summary="更新标签（管理员）")
async def admin_update_tag(
    uuid: str,
    body: AdminTagUpdateRequest,
    db: DbSession,
    admin: RequireAdmin,
    request: Request,
) -> dict:
    svc = _service(db, request)
    result = await svc.update_tag(
        uuid,
        name=body.name,
        color=body.color,
        admin_uuid=admin["uuid"],
    )
    await db.commit()
    return ok(result)


@router.delete("/admin/tags/{uuid}", summary="删除标签（管理员）")
async def admin_delete_tag(uuid: str, db: DbSession, admin: RequireAdmin, request: Request) -> dict:
    svc = _service(db, request)
    await svc.delete_tag(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok(None)


# =============================================================================
# User Data Views
# =============================================================================


@router.get("/admin/users/{uuid}/tasks", summary="用户任务列表（管理员）")
async def admin_list_user_tasks(
    uuid: str,
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    quadrant: int | None = Query(default=None, ge=1, le=4),
    completed: bool | None = Query(default=None),
) -> dict:
    svc = _service(db)
    result = await svc.list_user_tasks(
        user_uuid=uuid,
        page=page, page_size=pageSize,
        quadrant=quadrant, completed=completed,
    )
    return ok(result)


@router.get("/admin/users/{uuid}/tags", summary="用户标签列表（管理员）")
async def admin_list_user_tags(
    uuid: str,
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> dict:
    svc = _service(db)
    result = await svc.list_user_tags(
        user_uuid=uuid,
        page=page, page_size=pageSize,
    )
    return ok(result)
