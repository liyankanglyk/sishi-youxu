"""同步相关端点 —— Phase 2+ 实现。

已实现的功能：
- POST /sync/push — 将本地变更推送到服务端，支持 opId 级幂等
- GET /sync/pull — 拉取指定时间戳之后的变更（含 user 归属过滤）
- GET /sync/status — 公开时间校准端点

冲突检测：task upsert 时比较客户端 `updatedAt` 与服务端 `updated_at`，
客户端版本较旧时返回 `{status: "conflict", serverRecord: ...}` 让前端选择。

安全：所有 pull 端点按 user_uuid 过滤；所有 push 写入前校验实体归属，
防止跨用户操作。

事务：每条 op 用独立 SAVEPOINT 包裹，单条失败不影响整批。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from src.apps.user.schemas.v1.sync import SyncPushRequest
from src.apps.user.services.task_service import TaskService
from src.core.config import settings
from src.core.deps import CurrentUser, DbSession, RequiredUser
from src.core.exceptions import NotFoundException, ValidationException
from src.core.logger import get_logger
from src.core.redis import build_key, get_redis
from src.core.response import ok
from src.models.task import Tag, Task, TaskChecklist, TaskTag

logger = get_logger(__name__)

router = APIRouter(prefix="/sync", tags=["user-sync"])

# 同步操作的幂等性 TTL（24 小时）
_SYNC_IDEMPOTENCY_TTL = 86400
# 同步批量上限
_SYNC_OPS_MAX = 100
# pull since 最小接受时间（防止 DoS）
_PULL_SINCE_MIN = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _now() -> datetime:
    """统一的时间戳来源：UTC，aware。"""
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    """统一的 ISO 序列化：aware UTC，无 naive 出现。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_iso(s: Any) -> datetime | None:
    """解析客户端 ISO 时间字符串为 aware datetime。失败返回 None。"""
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


# =============================================================================
# 推送
# =============================================================================


@router.post(
    "/push",
    summary="推送变更",
    description="批量推送本地 ops 到服务端，支持 opId 级幂等 + 冲突检测",
)
async def push_sync(body: SyncPushRequest, current: RequiredUser, db: DbSession) -> dict:
    """将本地 ops 推送到服务端，按 opId 实现幂等。"""
    ops: list[dict] = [op.model_dump() for op in body.ops]

    if len(ops) > _SYNC_OPS_MAX:
        raise ValidationException(
            f"单次最多推送 {_SYNC_OPS_MAX} 条操作",
            code="VALIDATION_ERROR",
            detail={"ops": f"单次最多推送 {_SYNC_OPS_MAX} 条操作"},
        )

    redis = get_redis()
    results: list[dict] = []
    # 幂等缓存必须等整批 commit 成功后才写：写早了，一旦提交失败，
    # Redis 里会留下 "applied"，客户端重试命中缓存拿到 applied 就会把 op 出队，
    # 本地改动永久丢失、服务端从未落库。
    pending_idem: list[tuple[str, str]] = []
    user_uuid = current["uuid"]
    svc = TaskService(db)

    for op in ops:
        op_id = op.get("opId", "")
        if not op_id:
            results.append({
                "opId": "",
                "status": "rejected",
                "reason": "opId missing",
                "serverTime": _iso(_now()),
            })
            continue

        # 幂等性检查（修复 Bug：原 idem_key 不含 user_uuid，跨用户 opId 碰撞会读到对方缓存）
        idem_key = build_key("sync:op", user_uuid, op_id)
        cached = None
        if redis is not None:
            try:
                cached = await redis.get(idem_key)
            except Exception as e:
                logger.warning("[sync] redis get failed, fallback no-idempotency: %s", e)
                cached = None
        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            try:
                results.append(json.loads(cached))
                continue
            except (json.JSONDecodeError, TypeError):
                logger.warning("[sync] cached op result for %s corrupted, re-apply", op_id)

        entity = op.get("entity", "")
        action = op.get("action", "")
        payload = op.get("payload", {})

        # 每个 op 用独立 SAVEPOINT 隔离，失败不影响其他 op
        savepoint = None
        try:
            savepoint = await db.begin_nested()
            op_result = await _apply_op(db, svc, user_uuid, entity, action, payload)
            await savepoint.commit()
            op_result["opId"] = op_id
            op_result["status"] = op_result.get("status", "applied")
            op_result["serverTime"] = _iso(_now())

            # 缓存结果用于幂等 —— 这里只登记，等整批 commit 成功后统一写入
            pending_idem.append((idem_key, json.dumps(op_result, default=str)))
            results.append(op_result)
        except Exception as exc:
            logger.warning("sync op %s failed: %s", op_id, exc)
            if savepoint is not None:
                try:
                    await savepoint.rollback()
                except Exception:
                    pass
            results.append({
                "opId": op_id,
                "status": "rejected",
                "reason": str(exc),
                "serverTime": _iso(_now()),
            })

    try:
        await db.commit()
    except SQLAlchemyError as e:
        logger.error("[sync] final commit failed: %s", e)
        await db.rollback()
        # 整批提交失败时把所有未拒绝 op 标 rejected
        for r in results:
            if r.get("status") not in ("rejected", "conflict"):
                r["status"] = "rejected"
                r["reason"] = f"commit failed: {e}"
        # 提交失败就不写幂等缓存，下次重试会真正重新执行
        pending_idem.clear()
    else:
        # 只有真正落库后才写幂等缓存
        if redis is not None:
            for idem_cache_key, idem_value in pending_idem:
                try:
                    await redis.set(
                        idem_cache_key,
                        idem_value,
                        ex=_SYNC_IDEMPOTENCY_TTL,
                    )
                except Exception as e:
                    logger.warning("[sync] redis set failed (non-fatal): %s", e)

    return ok({
        "results": results,
        "serverTime": _iso(_now()),
    })


def _payload_str(payload: dict, camel: str, snake: str) -> str:
    """取 payload 里的关联 uuid。

    客户端的本地实体用 camelCase（LocalTaskTag.taskUuid / LocalChecklistItem.taskUuid），
    早期服务端只认 snake_case，于是 taskTag / checklistItems 的 op 一律被判为
    "task_uuid required" 而 rejected。这里两种写法都接受。
    """
    value = payload.get(camel)
    if not value:
        value = payload.get(snake)
    return value or ""


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
            uuid = payload.get("uuid") or ""
            if uuid:
                # 带 uuid：先查服务端是否存在
                existing = (await db.execute(
                    select(Task).where(
                        Task.uuid == uuid,
                        Task.user_uuid == user_uuid,
                    )
                )).scalar_one_or_none()

                if existing is None:
                    # 离线优先：客户端先在本地分配 UUID，服务端无此记录时
                    # 应当采纳客户端 UUID 创建，避免后续产生 UUID 冲突
                    result = await svc.create_task(user_uuid, payload, provided_uuid=uuid)
                    return {"serverRecord": result}

                if existing.deleted_at is not None:
                    raise ValidationException(
                        "任务已删除，请先恢复",
                        code="TASK_DELETED",
                    )

                # 冲突检测
                client_updated = _parse_iso(payload.get("updatedAt"))
                if client_updated is not None and existing.updated_at is not None:
                    server_updated = existing.updated_at
                    if server_updated.tzinfo is None:
                        server_updated = server_updated.replace(tzinfo=timezone.utc)
                    if client_updated < server_updated:
                        tags = await svc._get_task_tags(existing.uuid)
                        total_cl, completed_cl = await svc._get_checklist_counts(existing.uuid)
                        # _task_to_list_out 的第二个参数是 tag uuid 列表，不是 ORM 对象：
                        # 直接传 Tag 对象会被 FastAPI 用 vars() 序列化，_sa_instance_state 会漏进响应
                        tag_uuids = [t.uuid for t in tags]
                        return {
                            "status": "conflict",
                            "serverRecord": svc._task_to_list_out(
                                existing, tag_uuids, total_cl, completed_cl,
                            ),
                        }

                result = await svc.update_task(uuid, user_uuid, payload)
                return {"serverRecord": result}
            else:
                # 无 uuid：走 create 路径，服务端生成 uuid
                result = await svc.create_task(user_uuid, payload)
                return {"serverRecord": result}
        elif action == "delete":
            uuid = payload.get("uuid") or ""
            if not uuid:
                raise ValidationException("task uuid required", code="VALIDATION_ERROR")
            existing = (await db.execute(
                select(Task).where(
                    Task.uuid == uuid,
                    Task.user_uuid == user_uuid,
                )
            )).scalar_one_or_none()
            if existing is None:
                # 跨用户或不存在的 uuid 一律拒绝（不暴露存在性）
                raise NotFoundException("任务不存在或无权操作")
            if existing.deleted_at is not None:
                return {}
            await svc.delete_task(uuid, user_uuid)
            return {}

    elif entity == "tag":
        if action == "upsert":
            tag_uuid = payload.get("uuid") or ""
            tag_name = (payload.get("name") or "").strip()
            tag_color = payload.get("color") or "#cccccc"
            if not tag_name:
                raise ValidationException("tag name required", code="VALIDATION_ERROR")

            if tag_uuid:
                existing = (await db.execute(
                    select(Tag).where(Tag.uuid == tag_uuid)
                )).scalar_one_or_none()
                if existing is not None:
                    # 归属校验
                    if existing.user_uuid != user_uuid and not existing.is_preset:
                        raise ValidationException(
                            "无权修改此标签",
                            code="FORBIDDEN",
                        )
                    # 预设标签只允许改 color（不允许改 name）
                    if existing.is_preset and tag_name != existing.name:
                        raise ValidationException(
                            "预设标签名称不可修改",
                            code="PRESET_TAG_IMMUTABLE",
                        )
                    if "name" in payload:
                        existing.name = tag_name
                    if "color" in payload:
                        existing.color = tag_color
                    await db.flush()
                    return {"serverRecord": {
                        "uuid": existing.uuid,
                        "name": existing.name,
                        "color": existing.color,
                        "isPreset": existing.is_preset,
                    }}
            # 无 uuid 或 uuid 不存在：新建（服务端生成 uuid）
            tag = Tag(
                user_uuid=user_uuid,
                name=tag_name,
                color=tag_color,
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
            tag_uuid = payload.get("uuid") or ""
            if not tag_uuid:
                raise ValidationException("tag uuid required", code="VALIDATION_ERROR")
            existing = (await db.execute(
                select(Tag).where(Tag.uuid == tag_uuid)
            )).scalar_one_or_none()
            if existing is not None and not existing.is_preset:
                # 归属校验
                if existing.user_uuid != user_uuid:
                    raise ValidationException(
                        "无权删除此标签",
                        code="FORBIDDEN",
                    )
                if existing.deleted_at is None:
                    existing.deleted_at = _now()
                    await db.flush()
            return {}

    elif entity == "taskTag":
        task_uuid = _payload_str(payload, "taskUuid", "task_uuid")
        tag_uuid = _payload_str(payload, "tagUuid", "tag_uuid")
        if not task_uuid or not tag_uuid:
            raise ValidationException(
                "taskUuid and tagUuid required",
                code="VALIDATION_ERROR",
            )
        # 归属校验：task 必须属于 user_uuid
        task = (await db.execute(
            select(Task).where(
                Task.uuid == task_uuid,
                Task.user_uuid == user_uuid,
                Task.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if task is None:
            raise ValidationException(
                "任务不存在或无权操作",
                code="FORBIDDEN",
            )
        # 归属校验：tag 必须属于 user_uuid 或为预设
        tag = (await db.execute(
            select(Tag).where(
                Tag.uuid == tag_uuid,
                Tag.deleted_at.is_(None),
            )
        )).scalar_one_or_none()
        if tag is None or (tag.user_uuid != user_uuid and not tag.is_preset):
            raise ValidationException(
                "标签不存在或无权关联",
                code="FORBIDDEN",
            )

        if action == "upsert":
            existing = (await db.execute(
                select(TaskTag).where(
                    TaskTag.task_uuid == task_uuid,
                    TaskTag.tag_uuid == tag_uuid,
                )
            )).scalar_one_or_none()
            if existing is not None:
                existing.deleted_at = None
            else:
                db.add(TaskTag(task_uuid=task_uuid, tag_uuid=tag_uuid))
            await db.flush()
            return {"serverRecord": {
                "taskUuid": task_uuid,
                "tagUuid": tag_uuid,
            }}
        elif action == "delete":
            existing = (await db.execute(
                select(TaskTag).where(
                    TaskTag.task_uuid == task_uuid,
                    TaskTag.tag_uuid == tag_uuid,
                )
            )).scalar_one_or_none()
            if existing is None:
                raise NotFoundException("任务标签关联不存在或无权操作")
            await db.delete(existing)
            await db.flush()
            return {}

    elif entity == "checklistItems":
        if action == "upsert":
            cl_uuid = payload.get("uuid") or ""
            if not cl_uuid:
                raise ValidationException(
                    "checklist uuid required",
                    code="VALIDATION_ERROR",
                )
            cl_task_uuid = _payload_str(payload, "taskUuid", "task_uuid")
            if not cl_task_uuid:
                raise ValidationException(
                    "taskUuid required",
                    code="VALIDATION_ERROR",
                )
            cl_title = (payload.get("title") or "").strip()
            if not cl_title and "title" in payload:
                raise ValidationException(
                    "checklist title required",
                    code="VALIDATION_ERROR",
                )

            # 归属校验：task 必须属于 user_uuid
            task = (await db.execute(
                select(Task).where(
                    Task.uuid == cl_task_uuid,
                    Task.user_uuid == user_uuid,
                    Task.deleted_at.is_(None),
                )
            )).scalar_one_or_none()
            if task is None:
                raise ValidationException(
                    "任务不存在或无权操作",
                    code="FORBIDDEN",
                )

            existing = (await db.execute(
                select(TaskChecklist).where(
                    TaskChecklist.uuid == cl_uuid,
                )
            )).scalar_one_or_none()
            # 归属校验：existing checklist 必须挂在 user 的 task 上
            if existing is not None:
                owner_task = (await db.execute(
                    select(Task).where(
                        Task.uuid == existing.task_uuid,
                        Task.user_uuid == user_uuid,
                    )
                )).scalar_one_or_none()
                if owner_task is None:
                    raise ValidationException(
                        "检查项不存在或无权操作",
                        code="FORBIDDEN",
                    )
                if "title" in payload and cl_title:
                    existing.title = cl_title
                if "completed" in payload:
                    existing.completed = bool(payload["completed"])
                if "sortOrder" in payload:
                    existing.sort_order = payload["sortOrder"]
                existing.deleted_at = None  # 复活
                await db.flush()
                return {"serverRecord": {
                    "uuid": existing.uuid,
                    "taskUuid": existing.task_uuid,
                    "task_uuid": existing.task_uuid,  # 兼容旧字段名
                    "title": existing.title,
                    "completed": existing.completed,
                    "sortOrder": existing.sort_order,
                }}
            # 新建
            item = TaskChecklist(
                task_uuid=cl_task_uuid,
                title=payload.get("title", ""),
                completed=bool(payload.get("completed", False)),
                sort_order=payload.get("sortOrder", 0),
            )
            db.add(item)
            await db.flush()
            await db.refresh(item)
            return {"serverRecord": {
                "uuid": item.uuid,
                "taskUuid": item.task_uuid,
                "task_uuid": item.task_uuid,  # 兼容旧字段名
                "title": item.title,
                "completed": item.completed,
                "sortOrder": item.sort_order,
            }}
        elif action == "delete":
            cl_uuid = payload.get("uuid") or ""
            if not cl_uuid:
                raise ValidationException(
                    "checklist uuid required",
                    code="VALIDATION_ERROR",
                )
            existing = (await db.execute(
                select(TaskChecklist).where(TaskChecklist.uuid == cl_uuid)
            )).scalar_one_or_none()
            if existing is not None:
                # 归属校验
                owner_task = (await db.execute(
                    select(Task).where(
                        Task.uuid == existing.task_uuid,
                        Task.user_uuid == user_uuid,
                    )
                )).scalar_one_or_none()
                if owner_task is None:
                    raise ValidationException(
                        "无权删除此检查项",
                        code="FORBIDDEN",
                    )
                existing.deleted_at = _now()
                await db.flush()
            return {}

    raise ValidationException(
        f"unknown entity or action: {entity}/{action}",
        code="VALIDATION_ERROR",
    )


# =============================================================================
# 拉取
# =============================================================================


# 合法的 entity 子集（防止任意查询）
_VALID_ENTITIES = {"task", "tag", "taskTag", "checklistItems"}


@router.get(
    "/pull",
    summary="拉取变更",
    description="拉取指定时间后的服务端变更（user 归属过滤）",
)
async def pull_sync(
    current: RequiredUser,
    db: DbSession,
    since: str | None = Query(default=None, description="仅返回此时间后更新的记录（ISO 8601）"),
    entities: str | None = Query(default=None, description="实体类型，逗号分隔：task,tag,taskTag,checklistItems"),
) -> dict:
    user_uuid = current["uuid"]

    # 解析 entities，校验
    if entities:
        entity_set = {e.strip() for e in entities.split(",") if e.strip()}
        invalid = entity_set - _VALID_ENTITIES
        if invalid:
            raise ValidationException(
                f"非法 entity: {invalid}",
                code="VALIDATION_ERROR",
            )
    else:
        entity_set = set(_VALID_ENTITIES)

    # 解析 since（必填或默认全量，全量加 size 限制）
    since_dt: datetime | None = None
    if since:
        since_dt = _parse_iso(since)
        if since_dt is None:
            raise ValidationException(
                f"非法 since: {since}",
                code="VALIDATION_ERROR",
            )
    else:
        # 无 since 默认 30 天前，避免全表扫
        since_dt = _now().replace(microsecond=0)
        from datetime import timedelta
        since_dt = since_dt - timedelta(days=30)
        if since_dt < _PULL_SINCE_MIN:
            since_dt = _PULL_SINCE_MIN

    result: dict[str, Any] = {}

    if "task" in entity_set:
        task_stmt = select(Task).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None),  # 已删除的只出现在 deleted[] 中
            Task.updated_at >= since_dt,
        )
        tasks = (await db.execute(task_stmt)).scalars().all()

        deleted_stmt = select(Task.uuid).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_not(None),
            Task.updated_at >= since_dt,
        )
        deleted_rows = (await db.execute(deleted_stmt)).scalars().all()

        svc = TaskService(db)
        task_items = []
        for t in tasks:
            total_cl, completed_cl = await svc._get_checklist_counts(t.uuid)
            tag_stmt = select(TaskTag.tag_uuid).where(TaskTag.task_uuid == t.uuid)
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
            Tag.updated_at >= since_dt,
            ((Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True))),
        )
        tags = (await db.execute(tag_stmt)).scalars().all()
        result["tags"] = {
            "items": [
                {
                    "uuid": t.uuid,
                    "name": t.name,
                    "color": t.color,
                    "isPreset": t.is_preset,
                    "userUuid": t.user_uuid,
                    "updatedAt": _iso(t.updated_at),
                }
                for t in tags
            ],
        }

    if "taskTag" in entity_set:
        # 只拉当前用户 task 上的关联
        user_task_uuids = select(Task.uuid).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None),
        )
        tt_stmt = select(TaskTag).where(
            TaskTag.task_uuid.in_(user_task_uuids),
            TaskTag.updated_at >= since_dt,
        )
        task_tags = (await db.execute(tt_stmt)).scalars().all()
        result["taskTags"] = {
            "items": [
                {"taskUuid": tt.task_uuid, "tagUuid": tt.tag_uuid}
                for tt in task_tags
            ],
        }

    if "checklistItems" in entity_set:
        user_task_uuids = select(Task.uuid).where(
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None),
        )
        cl_stmt = select(TaskChecklist).where(
            TaskChecklist.task_uuid.in_(user_task_uuids),
            TaskChecklist.updated_at >= since_dt,
        )
        checklist_items = (await db.execute(cl_stmt)).scalars().all()
        result["checklistItems"] = {
            "items": [
                {
                    "uuid": c.uuid,
                    "taskUuid": c.task_uuid,
                    "title": c.title,
                    "completed": c.completed,
                    "sortOrder": c.sort_order,
                    "updatedAt": _iso(c.updated_at),
                }
                for c in checklist_items
            ],
        }

    result["serverAt"] = _iso(_now())
    return ok(result)


# =============================================================================
# 状态（公开）
# =============================================================================


@router.get("/status", summary="服务端时间", description="公开端点，返回服务端时间供客户端校准")
async def sync_status() -> dict:
    """用于客户端时间校准的公开端点。"""
    now = _now()
    return ok({
        "serverAt": _iso(now),
        "serverTimeMs": int(now.timestamp() * 1000),
        "timezone": settings.SERVER_TIMEZONE,
        "protocolVersion": 1,
    })