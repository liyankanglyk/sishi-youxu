"""Task CRUD endpoints — Phase 2 implementation.

Implemented:
- GET /tasks — list tasks (paginated, filtered)
- POST /tasks — create task
- GET /tasks/{uuid} — task detail
- PATCH /tasks/{uuid} — update task
- DELETE /tasks/{uuid} — soft delete
- POST /tasks/{uuid}/restore — restore
- POST /tasks/batch — batch operations
- Checklist CRUD sub-resource
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from src.apps.user.schemas.v1.task import (
    BatchActionRequest,
    ChecklistCreateRequest,
    ChecklistUpdateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
)
from src.apps.user.services.task_service import TaskService
from src.core.deps import DbSession, RequiredUser
from src.core.response import ok

router = APIRouter(prefix="/tasks", tags=["user-tasks"])


def _service(db: DbSession) -> TaskService:
    return TaskService(db)


# =============================================================================
# Task CRUD
# =============================================================================


@router.get("", summary="查询任务列表", description="分页查询当前用户的任务列表，支持关键词搜索和状态筛选")
async def list_tasks(
    current: RequiredUser,
    db: DbSession,
    since: Optional[datetime] = Query(default=None, description="仅返回指定时间后更新的任务（ISO 8601）"),
    completed: Optional[bool] = Query(default=None, description="筛选完成状态"),
    q: Optional[str] = Query(default=None, description="关键词搜索（标题）"),
    page: int = Query(default=1, ge=1, description="页码"),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
) -> dict:
    svc = _service(db)
    result = await svc.list_tasks(
        user_uuid=current["uuid"],
        since=since.isoformat() if since else None,
        completed=completed,
        q=q,
        page=page,
        page_size=pageSize,
    )
    return ok(result)


@router.post("", status_code=201, summary="创建任务", description="在四象限画布中创建新任务")
async def create_task(body: TaskCreateRequest, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.create_task(current["uuid"], body.model_dump())
    await db.commit()
    return ok(result)


@router.get("/{uuid}", summary="获取任务详情", description="根据 UUID 获取任务详细信息（含完整标签对象）")
async def get_task(uuid: str, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.get_task(uuid, current["uuid"])
    return ok(result)


@router.patch("/{uuid}", summary="更新任务", description="部分更新任务字段")
async def update_task(uuid: str, body: TaskUpdateRequest, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.update_task(uuid, current["uuid"], body.model_dump(exclude_unset=True))
    await db.commit()
    return ok(result)


@router.delete("/{uuid}", summary="删除任务", description="软删除任务（可恢复）")
async def delete_task(uuid: str, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    await svc.delete_task(uuid, current["uuid"])
    await db.commit()
    return ok(None)


@router.post("/{uuid}/restore", summary="恢复任务", description="恢复已软删除的任务")
async def restore_task(uuid: str, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.restore_task(uuid, current["uuid"])
    await db.commit()
    return ok(result)


@router.post("/batch", summary="批量操作任务", description="批量删除/恢复/移动/完成任务，支持幂等")
async def batch_tasks(body: BatchActionRequest, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.batch_tasks(
        user_uuid=current["uuid"],
        action=body.action,
        task_uuids=body.taskUuids,
        idempotency_key=body.idempotencyKey,
        quadrant=body.quadrant,
    )
    await db.commit()
    return ok(result)


# =============================================================================
# Checklist sub-resource
# =============================================================================

checklist_router = APIRouter(
    prefix="/tasks/{task_uuid}/checklist", tags=["user-checklist"]
)


@checklist_router.get("", summary="获取检查项列表", description="获取任务下的所有检查项")
async def list_checklist(
    task_uuid: str, current: RequiredUser, db: DbSession
) -> dict:
    svc = _service(db)
    result = await svc.list_checklist(task_uuid, current["uuid"])
    return ok(result)


@checklist_router.post("", status_code=201, summary="创建检查项", description="为任务添加检查项")
async def create_checklist_item(
    task_uuid: str, body: ChecklistCreateRequest, current: RequiredUser, db: DbSession
) -> dict:
    svc = _service(db)
    result = await svc.create_checklist_item(
        task_uuid, current["uuid"], body.model_dump()
    )
    await db.commit()
    return ok(result)


@checklist_router.patch("/{item_uuid}", summary="更新检查项", description="更新检查项的标题或完成状态")
async def update_checklist_item(
    task_uuid: str,
    item_uuid: str,
    body: ChecklistUpdateRequest,
    current: RequiredUser,
    db: DbSession,
) -> dict:
    svc = _service(db)
    result = await svc.update_checklist_item(
        task_uuid, item_uuid, current["uuid"], body.model_dump(exclude_unset=True)
    )
    await db.commit()
    return ok(result)


@checklist_router.delete("/{item_uuid}", summary="删除检查项", description="软删除检查项")
async def delete_checklist_item(
    task_uuid: str, item_uuid: str, current: RequiredUser, db: DbSession
) -> dict:
    svc = _service(db)
    await svc.delete_checklist_item(task_uuid, item_uuid, current["uuid"])
    await db.commit()
    return ok(None)
