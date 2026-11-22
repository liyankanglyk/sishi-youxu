"""任务领域 service —— Phase 2 实现。

包含：
- 任务 CRUD，支持软删除、标签关联、检查项聚合
- 批量操作（delete / restore / move / complete），支持幂等
- 检查项子资源 CRUD
- 用户数据隔离（所有查询均按 user_uuid 过滤）
- Redis 缓存加速（任务列表 30s TTL，写操作自动失效）
"""

from __future__ import annotations

import hashlib
import json
from datetime import date as date_type, datetime
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.cache import (
    TASK_LIST_TTL,
    TASK_DETAIL_TTL,
    cache_get,
    cache_set,
    cache_delete,
    invalidate_user_tasks,
)
from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from src.core.logger import get_logger
from src.core.redis import build_key, get_redis
from src.models.task import Tag, Task, TaskChecklist, TaskTag

logger = get_logger(__name__)

# 幂等缓存 TTL（24 小时）
_IDEMPOTENCY_TTL = 86400

# 象限中心坐标（urgencyLevel, importanceLevel）
_QUADRANT_CENTERS = {
    1: (2, 2),    # Q1: 紧急 + 重要
    2: (-2, 2),   # Q2: 不紧急 + 重要
    3: (2, -2),   # Q3: 紧急 + 不重要
    4: (-2, -2),  # Q4: 不紧急 + 不重要
}


class TaskService:
    """所有与任务相关的业务逻辑。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # 查询辅助
    # =========================================================================

    def _task_base_stmt(self, user_uuid: str):
        """用户任务的基础查询（未软删除）。"""
        return select(Task).where(
            Task.user_uuid == user_uuid, Task.deleted_at.is_(None)
        )

    async def _get_task_tags(self, task_uuid: str) -> list[Tag]:
        """获取任务关联的完整标签对象列表。"""
        stmt = (
            select(Tag)
            .join(
                TaskTag,
                TaskTag.tag_uuid == Tag.uuid,
            )
            .where(TaskTag.task_uuid == task_uuid, Tag.deleted_at.is_(None))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _get_checklist_counts(self, task_uuid: str) -> tuple[int, int]:
        """返回任务检查项的 (总数, 已完成数)。"""
        from sqlalchemy import cast, Integer as SAInteger
        stmt = select(
            func.count(TaskChecklist.uuid),
            func.coalesce(func.sum(cast(TaskChecklist.completed, SAInteger)), 0),
        ).where(
            TaskChecklist.task_uuid == task_uuid,
            TaskChecklist.deleted_at.is_(None),
        )
        row = (await self.db.execute(stmt)).one_or_none()
        if row is None:
            return 0, 0
        return int(row[0] or 0), int(row[1] or 0)

    async def _get_checklist_with_counts(
        self, task_uuid: str
    ) -> tuple[int, int, list[dict[str, Any]]]:
        """一次查询返回 (总数, 已完成数, 列表)，省掉 count 的 DB 往返。"""
        stmt = (
            select(TaskChecklist)
            .where(TaskChecklist.task_uuid == task_uuid, TaskChecklist.deleted_at.is_(None))
            .order_by(TaskChecklist.sort_order.asc(), TaskChecklist.created_at.asc())
        )
        items = (await self.db.execute(stmt)).scalars().all()
        total = len(items)
        completed = sum(1 for i in items if i.completed)
        serialized = [
            {"uuid": i.uuid, "title": i.title, "completed": i.completed,
             "sortOrder": i.sort_order,
             "createdAt": i.created_at.isoformat() if i.created_at else None,
             "updatedAt": i.updated_at.isoformat() if i.updated_at else None}
            for i in items
        ]
        return total, completed, serialized

    async def _validate_tags(
        self, user_uuid: str, tag_uuids: list[str]
    ) -> list[Tag]:
        """校验所有标签 UUID 是否存在且属于该用户（或为预设标签）。"""
        if not tag_uuids:
            return []
        stmt = select(Tag).where(
            Tag.uuid.in_(tag_uuids),
            Tag.deleted_at.is_(None),
            (Tag.user_uuid == user_uuid) | (Tag.is_preset.is_(True)),
        )
        tags = (await self.db.execute(stmt)).scalars().all()
        found_uuids = {t.uuid for t in tags}
        for tu in tag_uuids:
            if tu not in found_uuids:
                raise NotFoundException(
                    "指定的标签不存在",
                    code="TAG_NOT_FOUND",
                    detail={"tagUuid": tu},
                )
        return list(tags)

    async def _sync_task_tags(
        self, task_uuid: str, tag_uuids: list[str]
    ) -> None:
        """同步 TaskTag 关联表：硬删除旧记录，批量插入新记录。

        优化：使用 insert().values([...]) 批量插入代替逐条 add()，
        减少 DB 往返次数。
        """
        from sqlalchemy import insert

        await self.db.execute(
            delete(TaskTag).where(TaskTag.task_uuid == task_uuid)
        )

        if tag_uuids:
            await self.db.execute(
                insert(TaskTag),
                [{"task_uuid": task_uuid, "tag_uuid": tu} for tu in tag_uuids],
            )

    @staticmethod
    def _parse_date(value: str | date_type | None) -> date_type | None:
        """安全解析 ISO 日期字符串，接受 Pydantic 预解析的 date。"""
        if value is None or value == "":
            return None
        if isinstance(value, date_type):
            return value
        try:
            return date_type.fromisoformat(value)
        except (ValueError, TypeError):
            raise ValidationException(
                "日期格式错误，必须为 YYYY-MM-DD",
                code="VALIDATION_ERROR",
                detail={"dueDate": "截止日期格式必须为 YYYY-MM-DD"},
            )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        """安全解析 ISO datetime 字符串。"""
        if value is None:
            return None
        try:
            return datetime.fromisoformat(value)
        except (ValueError, TypeError):
            return None

    def _task_to_out(
        self,
        task: Task,
        tags: list[Tag] | None = None,
        total_cl: int = 0,
        completed_cl: int = 0,
        checklist_items: list[dict] | None = None,
    ) -> dict[str, Any]:
        """将 Task 序列化为详情接口的响应格式（标签为完整对象）。"""
        if tags is None:
            tags = []
        result: dict[str, Any] = {
            "uuid": task.uuid,
            "title": task.title,
            "urgencyLevel": task.urgency_level,
            "importanceLevel": task.importance_level,
            "dueDate": task.due_date.isoformat() if task.due_date else None,
            "recurrence": task.recurrence,
            "note": task.note,
            "tags": [
                {"uuid": t.uuid, "name": t.name, "color": t.color} for t in tags
            ],
            "checklistTotal": total_cl,
            "checklistCompleted": completed_cl,
            "completed": task.completed,
            "completedAt": task.completed_at.isoformat() if task.completed_at else None,
            "sortOrder": task.sort_order,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
        }
        if checklist_items is not None:
            result["checklistItems"] = checklist_items
        return result

    def _task_to_list_out(
        self,
        task: Task,
        tag_uuids: list[str] | None = None,
        total_cl: int = 0,
        completed_cl: int = 0,
        checklist_items: list[dict] | None = None,
    ) -> dict[str, Any]:
        """将 Task 序列化为列表接口的响应格式（标签为 UUID，含检查项列表）。"""
        if tag_uuids is None:
            tag_uuids = []
        result: dict[str, Any] = {
            "uuid": task.uuid,
            "title": task.title,
            "urgencyLevel": task.urgency_level,
            "importanceLevel": task.importance_level,
            "dueDate": task.due_date.isoformat() if task.due_date else None,
            "recurrence": task.recurrence,
            "note": task.note,
            "tags": tag_uuids,
            "checklistTotal": total_cl,
            "checklistCompleted": completed_cl,
            "completed": task.completed,
            "completedAt": task.completed_at.isoformat() if task.completed_at else None,
            "sortOrder": task.sort_order,
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
        }
        if checklist_items is not None:
            result["checklistItems"] = checklist_items
        return result

    # =========================================================================
    # 任务 CRUD
    # =========================================================================

    async def list_tasks(
        self,
        user_uuid: str,
        *,
        since: str | None = None,
        completed: bool | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """分页查询任务列表，支持筛选。Redis 缓存 30s。"""
        # 仅缓存无筛选的第 1 页（最频繁的查询）；筛选/翻页直接查 DB
        is_plain_first_page = (since is None and completed is None
                               and not q and page == 1 and page_size == 20)
        if is_plain_first_page:
            cached = await cache_get("tasks", user_uuid)
            if cached is not None:
                return cached

        # 构建基础条件
        conditions = [Task.user_uuid == user_uuid, Task.deleted_at.is_(None)]

        if since is not None:
            since_dt = self._parse_datetime(since)
            if since_dt:
                conditions.append(Task.updated_at >= since_dt)

        if completed is not None:
            conditions.append(Task.completed == completed)

        if q:
            conditions.append(Task.title.ilike(f"%{q}%"))

        # 直接 COUNT，避免子查询
        count_stmt = select(func.count(Task.uuid)).where(*conditions)
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # 分页数据
        stmt = (
            select(Task)
            .where(*conditions)
            .order_by(Task.sort_order.asc(), Task.created_at.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        if not rows:
            return {"items": [], "meta": {"total": total, "page": page,
                    "pageSize": page_size, "hasMore": False}}

        task_uuids = [t.uuid for t in rows]

        # 批量查标签（1 次代替 N 次）
        tag_map: dict[str, list[str]] = {}
        tag_rows = (await self.db.execute(
            select(TaskTag.task_uuid, TaskTag.tag_uuid).where(
                TaskTag.task_uuid.in_(task_uuids))
        )).all()
        for tu, gu in tag_rows:
            tag_map.setdefault(tu, []).append(gu)

        # 批量查检查项（1 次查出所有 items，含计数）
        cl_items = (await self.db.execute(
            select(TaskChecklist)
            .where(TaskChecklist.task_uuid.in_(task_uuids),
                   TaskChecklist.deleted_at.is_(None))
            .order_by(TaskChecklist.sort_order.asc(), TaskChecklist.created_at.asc())
        )).scalars().all()

        cl_map: dict[str, tuple[int, int, list[dict]]] = {}
        for item in cl_items:
            if item.task_uuid not in cl_map:
                cl_map[item.task_uuid] = [0, 0, []]
            entry = cl_map[item.task_uuid]
            entry[0] += 1  # total
            if item.completed:
                entry[1] += 1  # completed
            entry[2].append({
                "uuid": item.uuid, "title": item.title,
                "completed": item.completed, "sortOrder": item.sort_order,
                "createdAt": item.created_at.isoformat() if item.created_at else None,
                "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
            })

        items = []
        for task in rows:
            tag_uuids = tag_map.get(task.uuid, [])
            total_cl, completed_cl, checklist_data = cl_map.get(task.uuid, (0, 0, []))
            items.append(self._task_to_list_out(
                task, tag_uuids, total_cl, completed_cl,
                checklist_items=checklist_data,
            ))

        result = {"items": items, "meta": {"total": total, "page": page,
                "pageSize": page_size, "hasMore": (page * page_size) < total}}

        # 缓存无筛选第 1 页（最频繁的查询）
        if is_plain_first_page:
            await cache_set("tasks", user_uuid, value=result, ttl=TASK_LIST_TTL)

        return result

    async def get_task(self, uuid: str, user_uuid: str) -> dict[str, Any]:
        """获取任务详情（含完整标签对象 + 检查项列表）。"""
        stmt = self._task_base_stmt(user_uuid).where(Task.uuid == uuid)
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在或已删除", code="TASK_NOT_FOUND")

        tags = await self._get_task_tags(uuid)
        total_cl, completed_cl, checklist_items = await self._get_checklist_with_counts(uuid)
        return self._task_to_out(task, tags, total_cl, completed_cl, checklist_items)

    async def create_task(
        self, user_uuid: str, data: dict[str, Any], provided_uuid: str | None = None,
    ) -> dict[str, Any]:
        """创建新任务，可选关联标签。

        优化：跳过冗余的标签反查和检查项计数（新任务必然 0/0），
        减少 2 次 DB 往返。

        provided_uuid: 离线同步时由客户端指定的 UUID。
        """
        title = (data.get("title") or "").strip()
        if not title:
            raise ValidationException(
                "任务标题不能为空",
                code="VALIDATION_ERROR",
                detail={"title": "任务标题不能为空"},
            )
        if len(title) > 200:
            raise ValidationException(
                "任务标题不能超过 200 字符",
                code="VALIDATION_ERROR",
                detail={"title": "任务标题长度必须在 1-200 字符之间"},
            )

        urgency_level = int(data.get("urgencyLevel", 0))
        importance_level = int(data.get("importanceLevel", 0))
        if not (-4 <= urgency_level <= 4) or not (-4 <= importance_level <= 4):
            raise ValidationException(
                "紧急度/重要度必须在 -4 到 4 之间",
                code="VALIDATION_ERROR",
                detail={
                    "urgencyLevel": "紧急度必须在 -4 到 4 之间",
                    "importanceLevel": "重要度必须在 -4 到 4 之间",
                },
            )

        tag_uuids = data.get("tags") or data.get("tag_uuids") or []
        # _validate_tags 返回已验证的 Tag 对象，避免后续再查一次
        validated_tags = await self._validate_tags(user_uuid, tag_uuids)

        task_kwargs: dict[str, Any] = {
            "user_uuid": user_uuid,
            "title": title,
            "urgency_level": urgency_level,
            "importance_level": importance_level,
            "due_date": self._parse_date(data.get("dueDate")),
            "recurrence": data.get("recurrence"),
            "note": data.get("note"),
            "sort_order": data.get("sortOrder", 0),
            "remind_at": self._parse_datetime(data.get("remindAt")),
            "remind_offset_minutes": data.get("remindOffsetMinutes"),
        }
        if provided_uuid:
            task_kwargs["uuid"] = provided_uuid

        task = Task(**task_kwargs)

        self.db.add(task)
        await self.db.flush()

        if tag_uuids:
            await self._sync_task_tags(task.uuid, tag_uuids)
            await self.db.flush()

        # 新任务：标签即刚刚关联的，检查项必然为 0——无需额外 DB 查询
        await invalidate_user_tasks(user_uuid)
        return self._task_to_out(task, validated_tags, 0, 0)

    async def update_task(
        self, uuid: str, user_uuid: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """更新任务字段（部分更新）。"""
        stmt = self._task_base_stmt(user_uuid).where(Task.uuid == uuid)
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在或已删除", code="TASK_NOT_FOUND")

        changed = False

        if "title" in data:
            title = (data["title"] or "").strip()
            if not title or len(title) > 200:
                raise ValidationException(
                    "任务标题长度必须在 1-200 字符之间",
                    code="VALIDATION_ERROR",
                    detail={"title": "任务标题长度必须在 1-200 字符之间"},
                )
            task.title = title
            changed = True

        if "urgencyLevel" in data:
            ul = int(data["urgencyLevel"])
            if not (-4 <= ul <= 4):
                raise ValidationException(
                    "紧急度必须在 -4 到 4 之间",
                    code="VALIDATION_ERROR",
                    detail={"urgencyLevel": "紧急度必须在 -4 到 4 之间"},
                )
            task.urgency_level = ul
            changed = True

        if "importanceLevel" in data:
            il = int(data["importanceLevel"])
            if not (-4 <= il <= 4):
                raise ValidationException(
                    "重要度必须在 -4 到 4 之间",
                    code="VALIDATION_ERROR",
                    detail={"importanceLevel": "重要度必须在 -4 到 4 之间"},
                )
            task.importance_level = il
            changed = True

        if "dueDate" in data:
            task.due_date = self._parse_date(data["dueDate"])
            changed = True

        if "recurrence" in data:
            task.recurrence = data["recurrence"]
            changed = True

        if "note" in data:
            task.note = data["note"]
            changed = True

        if "completed" in data:
            task.completed = bool(data["completed"])
            if task.completed:
                task.completed_at = task.completed_at or datetime.utcnow()
            else:
                task.completed_at = None
            changed = True

        if "completedAt" in data:
            task.completed_at = self._parse_datetime(data["completedAt"])
            changed = True

        if "sortOrder" in data:
            task.sort_order = int(data["sortOrder"])
            changed = True

        if "remindAt" in data:
            task.remind_at = self._parse_datetime(data["remindAt"])
            changed = True

        if "remindOffsetMinutes" in data:
            task.remind_offset_minutes = data["remindOffsetMinutes"]
            changed = True

        # 标签更新
        tag_key = "tags" if "tags" in data else ("tag_uuids" if "tag_uuids" in data else None)
        if tag_key:
            tag_uuids = data[tag_key] or []
            await self._validate_tags(user_uuid, tag_uuids)
            await self._sync_task_tags(uuid, tag_uuids)
            changed = True

        if changed:
            await self.db.flush()

        tags = await self._get_task_tags(uuid)
        total_cl, completed_cl = await self._get_checklist_counts(uuid)
        await invalidate_user_tasks(user_uuid)
        return self._task_to_out(task, tags, total_cl, completed_cl)

    async def delete_task(self, uuid: str, user_uuid: str) -> None:
        """软删除任务。"""
        stmt = self._task_base_stmt(user_uuid).where(Task.uuid == uuid)
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在或已删除", code="TASK_NOT_FOUND")
        task.deleted_at = datetime.utcnow()
        await self.db.flush()
        await invalidate_user_tasks(user_uuid)

    async def restore_task(
        self, uuid: str, user_uuid: str
    ) -> dict[str, Any]:
        """恢复软删除的任务。"""
        stmt = select(Task).where(
            Task.uuid == uuid,
            Task.user_uuid == user_uuid,
        )
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在", code="TASK_NOT_FOUND")
        if task.deleted_at is None:
            raise ConflictException(
                "任务未删除，无需恢复",
                code="RESOURCE_DELETED",
            )

        task.deleted_at = None
        restored_at = datetime.utcnow()
        await self.db.flush()
        await invalidate_user_tasks(user_uuid)

        return {
            "uuid": task.uuid,
            "title": task.title,
            "status": "restored",
            "restoredAt": restored_at.isoformat(),
        }

    # =========================================================================
    # 批量操作
    # =========================================================================

    async def batch_tasks(
        self,
        user_uuid: str,
        action: str,
        task_uuids: list[str],
        idempotency_key: str,
        quadrant: int | None = None,
    ) -> dict[str, Any]:
        """批量操作，支持幂等。"""
        if not task_uuids:
            raise ValidationException(
                "任务 UUID 列表不能为空",
                code="VALIDATION_ERROR",
                detail={"taskUuids": "任务 UUID 列表不能为空"},
            )

        if action not in {"delete", "restore", "move", "complete"}:
            raise ValidationException(
                f"不支持的批量操作: {action}",
                code="VALIDATION_ERROR",
                detail={"action": f"不支持的批量操作: {action}"},
            )

        if action == "move" and quadrant is None:
            raise ValidationException(
                "action 为 move 时必须指定 quadrant",
                code="VALIDATION_ERROR",
                detail={"action": "action 为 move 时必须指定 quadrant"},
            )

        # 通过 Redis 进行幂等性检查
        # key 必须带 user_uuid：否则不同用户用同一个 idempotencyKey 会读到对方的缓存结果，
        # 结果里还带着别人的 taskUuids（sync 接口已修过同样的问题，这里要同步）
        redis = get_redis()
        idem_key = build_key("idempotency", user_uuid, idempotency_key)
        cached = None
        try:
            cached = await redis.get(idem_key)
        except Exception:
            # Redis 不可用 → 退化为不幂等，而不是让整个批量操作 500
            cached = None
        if cached is not None:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            return json.loads(cached)

        if len(task_uuids) > 200:
            raise ValidationException(
                "单次批量操作最多 200 个任务",
                code="VALIDATION_ERROR",
                detail={"taskUuids": "单次批量操作最多 200 个任务"},
            )

        # 查找属于该用户的匹配任务
        stmt = select(Task).where(
            Task.uuid.in_(task_uuids),
            Task.user_uuid == user_uuid,
        )
        task_rows = (await self.db.execute(stmt)).scalars().all()
        found_uuids = {t.uuid for t in task_rows}

        not_found = [u for u in task_uuids if u not in found_uuids]

        if action == "delete":
            for t in task_rows:
                if t.deleted_at is None:
                    t.deleted_at = datetime.utcnow()

        elif action == "restore":
            for t in task_rows:
                if t.deleted_at is not None:
                    t.deleted_at = None

        elif action == "complete":
            now = datetime.utcnow()
            for t in task_rows:
                t.completed = True
                t.completed_at = now

        elif action == "move":
            if quadrant in _QUADRANT_CENTERS:
                ul, il = _QUADRANT_CENTERS[quadrant]
                for t in task_rows:
                    t.urgency_level = ul
                    t.importance_level = il

        await self.db.flush()
        await invalidate_user_tasks(user_uuid)

        affected = list(found_uuids)
        result: dict[str, Any] = {
            "affected": len(affected),
            "taskUuids": affected,
        }
        if action == "move":
            result["movedToQuadrant"] = quadrant

        if not_found:
            result["notFoundUuids"] = not_found

        # 先提交再写幂等缓存：顺序反了的话，一旦提交失败而缓存已写成"成功"，
        # 客户端重试会命中缓存拿到成功结果，实际操作却从未落库。
        await self.db.commit()

        # 缓存幂等结果（24 小时）
        try:
            await redis.set(
                idem_key, json.dumps(result, default=str), ex=_IDEMPOTENCY_TTL
            )
        except Exception:
            # 缓存失败不影响本次操作结果，只是失去幂等保护
            pass

        return result

    # =========================================================================
    # 检查项
    # =========================================================================

    async def _get_task_or_404(self, task_uuid: str, user_uuid: str) -> Task:
        """根据 UUID 与用户获取任务，不存在则抛 TASK_NOT_FOUND。"""
        stmt = select(Task).where(
            Task.uuid == task_uuid,
            Task.user_uuid == user_uuid,
            Task.deleted_at.is_(None),
        )
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在或已删除", code="TASK_NOT_FOUND")
        return task

    async def list_checklist(
        self, task_uuid: str, user_uuid: str
    ) -> dict[str, Any]:
        """列出任务的检查项列表。"""
        # 归属校验：task 必须属于当前用户，否则会列出他人任务的检查项
        await self._get_task_or_404(task_uuid, user_uuid)
        stmt = (
            select(TaskChecklist)
            .where(
                TaskChecklist.task_uuid == task_uuid,
                TaskChecklist.deleted_at.is_(None),
            )
            .order_by(
                TaskChecklist.sort_order.asc(), TaskChecklist.created_at.asc()
            )
        )
        items = (await self.db.execute(stmt)).scalars().all()

        serialized = [
            {
                "uuid": i.uuid,
                "title": i.title,
                "completed": i.completed,
                "sortOrder": i.sort_order,
                "createdAt": i.created_at.isoformat() if i.created_at else None,
                "updatedAt": i.updated_at.isoformat() if i.updated_at else None,
            }
            for i in items
        ]

        return {
            "items": serialized,
            "meta": {
                "total": len(serialized),
                "page": 1,
                "pageSize": max(len(serialized), 20),
                "hasMore": False,
            },
        }

    async def create_checklist_item(
        self, task_uuid: str, user_uuid: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """创建检查项。"""
        await self._get_task_or_404(task_uuid, user_uuid)

        title = (data.get("title") or "").strip()
        if not title or len(title) > 255:
            raise ValidationException(
                "检查项标题长度必须在 1-255 字符之间",
                code="VALIDATION_ERROR",
                detail={"title": "检查项标题长度必须在 1-255 字符之间"},
            )

        item = TaskChecklist(
            task_uuid=task_uuid,
            title=title,
            completed=bool(data.get("completed", False)),
            sort_order=data.get("sortOrder", 0),
        )
        self.db.add(item)
        await self.db.flush()

        return {
            "uuid": item.uuid,
            "title": item.title,
            "completed": item.completed,
            "sortOrder": item.sort_order,
            "createdAt": item.created_at.isoformat() if item.created_at else None,
            "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
        }

    async def update_checklist_item(
        self,
        task_uuid: str,
        item_uuid: str,
        user_uuid: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """更新检查项。"""
        # 归属校验：task 必须属于当前用户
        await self._get_task_or_404(task_uuid, user_uuid)
        stmt = select(TaskChecklist).where(
            TaskChecklist.uuid == item_uuid,
            TaskChecklist.task_uuid == task_uuid,
            TaskChecklist.deleted_at.is_(None),
        )
        item = (await self.db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise NotFoundException("检查项不存在", code="CHECKLIST_NOT_FOUND")

        if "title" in data:
            title = (data["title"] or "").strip()
            if not title or len(title) > 255:
                raise ValidationException(
                    "检查项标题长度必须在 1-255 字符之间",
                    code="VALIDATION_ERROR",
                    detail={"title": "检查项标题长度必须在 1-255 字符之间"},
                )
            item.title = title

        if "completed" in data:
            item.completed = bool(data["completed"])

        if "sortOrder" in data:
            item.sort_order = int(data["sortOrder"])

        await self.db.flush()

        return {
            "uuid": item.uuid,
            "title": item.title,
            "completed": item.completed,
            "sortOrder": item.sort_order,
            "createdAt": item.created_at.isoformat() if item.created_at else None,
            "updatedAt": item.updated_at.isoformat() if item.updated_at else None,
        }

    async def delete_checklist_item(
        self, task_uuid: str, item_uuid: str, user_uuid: str
    ) -> None:
        """软删除检查项。"""
        # 归属校验：task 必须属于当前用户
        await self._get_task_or_404(task_uuid, user_uuid)
        stmt = select(TaskChecklist).where(
            TaskChecklist.uuid == item_uuid,
            TaskChecklist.task_uuid == task_uuid,
            TaskChecklist.deleted_at.is_(None),
        )
        item = (await self.db.execute(stmt)).scalar_one_or_none()
        if item is None:
            raise NotFoundException("检查项不存在", code="CHECKLIST_NOT_FOUND")

        item.deleted_at = datetime.utcnow()
        await self.db.flush()


__all__ = ["TaskService"]
