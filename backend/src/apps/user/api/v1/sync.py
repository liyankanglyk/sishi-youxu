"""同步相关端点 —— Phase 2 实现。

已实现的功能：
- POST /sync/push — 将本地变更推送到服务端
- GET /sync/pull — 拉取指定时间戳之后的变更
- GET /sync/status — 公开时间校准端点
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import delete, select

from src.apps.user.schemas.v1.sync import SyncPushRequest
from src.apps.user.services.task_service import TaskService
from src.core.config import settings
from src.core.deps import CurrentUser, DbSession, RequiredUser
from src.core.exceptions import ValidationException
from src.core.logger import get_logger
from src.core.redis import build_key, get_redis
from src.core.response import ok
from src.models.task import Tag, Task, TaskChecklist, TaskTag

logger = get_logger(__name__)

router = APIRouter(prefix="/sync", tags=["user-sync"])

# 同步操作的幂等性 TTL（24 小时）
_SYNC_IDEMPOTENCY_TTL = 86400


# =============================================================================
# 推送
# =============================================================================


@router.post("/push", summary="推送变更", description="批量推送本地 ops 到服务端，支持 opId 级幂等")
async def push_sync(body: SyncPushRequest, current: RequiredUser, db: DbSession) -> dict:
    """将本地 ops 推送到服务端，按 opId 实现幂等。"""
    ops: list[dict] = [op.model_dump() for op in body.ops]

    if len(ops) > 100:
        raise ValidationException(
            "单次最多推送 100 条操作",
            code="VALIDATION_ERROR",
            detail={"ops": "单次最多 100 条操作"},
        )

    redis = get_redis()
    results: list[dict] = []
    user_uuid = current["uuid"]
    svc = TaskService(db)

    for op in ops:
        op_id = op.get("opId", "")
        if not op_id:
            results.append({"opId": "", "status": "rejected", "reason": "opId missing"})
            continue

        # 幂等性检查
        idem_key = build_key("sync:op", op_id)
        cached = await redis.get(idem_key)
        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            results.append(json.loads(cached))
            continue

        entity = op.get("entity", "")
        action = op.get("action", "")
        payload = op.get("payload", {})

        try:
            op_result = await _apply_op(db, svc, user_uuid, entity, action, payload)
            op_result["opId"] = op_id
            op_result["status"] = "applied"
            op_result["serverTime"] = datetime.utcnow().isoformat()

            # 缓存结果用于幂等
            await redis.set(
                idem_key,
                json.dumps(op_result, default=str),
                ex=_SYNC_IDEMPOTENCY_TTL,
            )
            results.append(op_result)
        except Exception as exc:
            logger.warning("sync op %s failed: %s", op_id, exc)
            results.append({
                "opId": op_id,
                "status": "rejected",
                "reason": str(exc),
                "serverTime": datetime.utcnow().isoformat(),
            })

    await db.commit()

    return ok({
        "results": results,
        "serverTime": datetime.utcnow().isoformat(),
    })


async def _apply_op(
    db: Any,
    svc: TaskService,
    user_uuid: str,
    entity: str,
    action: str,
    payload: dict,
) -> dict:
    """根据实体类型应用单个同步操作。"""
    if entity == "task":
        if action == "upsert":
            if payload.get("uuid"):
                # 尝试更新，失败回退为创建
                try:
                    result = await svc.update_task(payload["uuid"], user_uuid, payload)
                    return {"serverRecord": result}
                except Exception:
                    result = await svc.create_task(user_uuid, payload)
                    return {"serverRecord": result}
            else:
                result = await svc.create_task(user_uuid, payload)
                return {"serverRecord": result}
        elif action == "delete":
            await svc.delete_task(payload.get("uuid", ""), user_uuid)
            return {}

    elif entity == "tag":
        if action == "upsert":
            stmt = select(Tag).where(
                Tag.uuid == payload.get("uuid", ""),
                Tag.user_uuid == user_uuid,
                Tag.deleted_at.is_(None),
            )
            existing = (await db.execute(stmt)).scalar_one_or_none()
            if existing is not None:
                if "name" in payload:
                    existing.name = payload["name"]
                if "color" in payload:
                    existing.color = payload["color"]
                await db.flush()
                return {"serverRecord": {
                    "uuid": existing.uuid,
                    "name": existing.name,
                    "color": existing.color,
                    "isPreset": existing.is_preset,
                }}
            else:
                tag = Tag(
                    user_uuid=user_uuid,
                    name=payload.get("name", ""),
                    color=payload.get("color", "#cccccc"),
                    is_preset=False,
                )
                db.add(tag)
                await db.flush()
                await db.refresh(tag)
                return {"serverRecord": {
                    "uuid": tag.uuid,
                    "name": tag.name,
                    "color": tag.color,
                    "isPreset": tag.is_preset,
                }}
        elif action == "delete":
            stmt = select(Tag).where(
                Tag.uuid == payload.get("uuid", ""),
                Tag.user_uuid == user_uuid,
                Tag.deleted_at.is_(None),
            )
            tag = (await db.execute(stmt)).scalar_one_or_none()
            if tag is not None and not tag.is_preset:
                tag.deleted_at = datetime.utcnow()
                await db.flush()
            return {}

    elif entity == "taskTag":
        task_uuid = payload.get("task_uuid", "")
        tag_uuid = payload.get("tag_uuid", "")
        if action == "upsert":
            existing = await db.execute(
                select(TaskTag).where(
                    TaskTag.task_uuid == task_uuid,
                    TaskTag.tag_uuid == tag_uuid,
                )
            )
            link = existing.scalar_one_or_none()
            if link is not None:
                link.deleted_at = None
            else:
                db.add(TaskTag(task_uuid=task_uuid, tag_uuid=tag_uuid))
            await db.flush()
        elif action == "delete":
            await db.execute(
                delete(TaskTag).where(
                    TaskTag.task_uuid == task_uuid,
                    TaskTag.tag_uuid == tag_uuid,
                )
            )
            await db.flush()
        return {}

    elif entity == "checklistItems":
        if action == "upsert":
            cl_uuid = payload.get("uuid", "")
            if cl_uuid:
                existing = await db.execute(
                    select(TaskChecklist).where(
                        TaskChecklist.uuid == cl_uuid,
                        TaskChecklist.deleted_at.is_(None),
                    )
                )
                item = existing.scalar_one_or_none()
                if item is not None:
                    if "title" in payload:
                        item.title = payload["title"]
                    if "completed" in payload:
                        item.completed = payload["completed"]
                    if "sortOrder" in payload:
                        item.sort_order = payload["sortOrder"]
                    await db.flush()
                    return {"serverRecord": {
                        "uuid": item.uuid,
                        "task_uuid": item.task_uuid,
                        "title": item.title,
                        "completed": item.completed,
                        "sortOrder": item.sort_order,
                    }}
            # 创建
            item = TaskChecklist(
                task_uuid=payload.get("task_uuid", ""),
                title=payload.get("title", ""),
                completed=bool(payload.get("completed", False)),
                sort_order=payload.get("sortOrder", 0),
            )
            db.add(item)
            await db.flush()
            await db.refresh(item)
            return {"serverRecord": {
                "uuid": item.uuid,
                "task_uuid": item.task_uuid,
                "title": item.title,
                "completed": item.completed,
                "sortOrder": item.sort_order,
            }}
        elif action == "delete":
            existing = await db.execute(
                select(TaskChecklist).where(
                    TaskChecklist.uuid == payload.get("uuid", ""),
                    TaskChecklist.deleted_at.is_(None),
                )
            )
            item = existing.scalar_one_or_none()
            if item is not None:
                item.deleted_at = datetime.utcnow()
                await db.flush()
            return {}

    return {}


# =============================================================================
# 拉取
# =============================================================================


@router.get("/pull", summary="拉取变更", description="拉取指定时间后的服务端变更")
async def pull_sync(
    current: RequiredUser,
    db: DbSession,
    since: str | None = Query(default=None, description="仅返回此时间后更新的记录（ISO 8601）"),
    entities: str | None = Query(default=None, description="实体类型，逗号分隔：task,tag,taskTag,checklistItems"),
) -> dict:
    user_uuid = current["uuid"]
    entity_set = set((entities or "").split(",")) if entities else {"task", "tag", "taskTag", "checklistItems"}

    result: dict[str, Any] = {}
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except (ValueError, TypeError):
            pass

    if "task" in entity_set:
        task_stmt = select(Task).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None),
        )
        if since_dt:
            task_stmt = task_stmt.where(Task.updated_at >= since_dt)
        tasks = (await db.execute(task_stmt)).scalars().all()

        # 同时获取自该时间戳以来被软删除的任务
        deleted_stmt = select(Task.uuid).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None) == False,
        )
        if since_dt:
            deleted_stmt = deleted_stmt.where(Task.updated_at >= since_dt)
        deleted_rows = (await db.execute(deleted_stmt)).scalars().all()

        svc = TaskService(db)
        task_items = []
        for t in tasks:
            total_cl, completed_cl = await svc._get_checklist_counts(t.uuid)
            tag_stmt = select(TaskTag.tag_uuid).where(
                TaskTag.task_uuid == t.uuid,
            )
            tag_res = await db.execute(tag_stmt)
            tag_uuids = [r[0] for r in tag_res.all()]
            task_items.append(svc._task_to_list_out(t, tag_uuids, total_cl, completed_cl))

        result["tasks"] = {
            "items": task_items,
            "deleted": list(deleted_rows),
        }

    if "tag" in entity_set:
        tag_stmt = select(Tag).where(
            Tag.deleted_at.is_(None),
            (Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True)),
        )
        if since_dt:
            tag_stmt = tag_stmt.where(Tag.updated_at >= since_dt)
        tags = (await db.execute(tag_stmt)).scalars().all()
        result["tags"] = {
            "items": [
                {
                    "uuid": t.uuid,
                    "name": t.name,
                    "color": t.color,
                    "isPreset": t.is_preset,
                    "userUuid": t.user_uuid,
                    "updatedAt": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tags
            ],
        }

    if "taskTag" in entity_set:
        tt_stmt = select(TaskTag)
        if since_dt:
            tt_stmt = tt_stmt.where(TaskTag.updated_at >= since_dt)
        task_tags = (await db.execute(tt_stmt)).scalars().all()
        result["taskTags"] = {
            "items": [
                {"taskUuid": tt.task_uuid, "tagUuid": tt.tag_uuid}
                for tt in task_tags
            ],
        }

    if "checklistItems" in entity_set:
        cl_stmt = select(TaskChecklist).where(TaskChecklist.deleted_at.is_(None))
        if since_dt:
            cl_stmt = cl_stmt.where(TaskChecklist.updated_at >= since_dt)
        checklist_items = (await db.execute(cl_stmt)).scalars().all()
        result["checklistItems"] = {
            "items": [
                {
                    "uuid": c.uuid,
                    "taskUuid": c.task_uuid,
                    "title": c.title,
                    "completed": c.completed,
                    "sortOrder": c.sort_order,
                    "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
                }
                for c in checklist_items
            ],
        }

    result["serverAt"] = datetime.utcnow().isoformat()
    return ok(result)


# =============================================================================
# 状态（公开）
# =============================================================================


@router.get("/status", summary="服务端时间", description="公开端点，返回服务端时间供客户端校准")
async def sync_status() -> dict:
    """用于客户端时间校准的公开端点。"""
    now = datetime.now(timezone.utc)
    return ok({
        "serverAt": now.isoformat(),
        "serverTimeMs": int(now.timestamp() * 1000),
        "timezone": settings.SERVER_TIMEZONE,
    })
