"""Task domain service — Phase 2 implementation.

Covers:
- Task CRUD with soft-delete, tag linking, checklist aggregation
- Batch operations (delete / restore / move / complete) with idempotency
- Checklist sub-resource CRUD
- User data isolation (all queries filter by user_uuid)
"""

from __future__ import annotations

import json
from datetime import date as date_type, datetime
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from src.core.logger import get_logger
from src.core.redis import build_key, get_redis
from src.models.task import Tag, Task, TaskChecklist, TaskTag

logger = get_logger(__name__)

# Idempotency cache TTL (24 hours)
_IDEMPOTENCY_TTL = 86400

# Quadrant center coordinates (urgencyLevel, importanceLevel)
_QUADRANT_CENTERS = {
    1: (2, 2),    # Q1: urgent + important
    2: (-2, 2),   # Q2: not urgent + important
    3: (2, -2),   # Q3: urgent + not important
    4: (-2, -2),  # Q4: not urgent + not important
}


class TaskService:
    """All task-related business logic."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # Query helpers
    # =========================================================================

    def _task_base_stmt(self, user_uuid: str):
        """Base select for tasks belonging to user, not soft-deleted."""
        return select(Task).where(
            Task.user_uuid == user_uuid, Task.deleted_at.is_(None)
        )

    async def _get_task_tags(self, task_uuid: str) -> list[Tag]:
        """Get full tag objects for a task."""
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
        """Return (total, completed) for a task's checklist items.

        Cast the boolean column to Integer before summing — otherwise
        SQLAlchemy may return a Python bool for single-item sums, which
        JSON-serialises to ``true`` instead of a number.
        """
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

    async def _validate_tags(
        self, user_uuid: str, tag_uuids: list[str]
    ) -> list[Tag]:
        """Validate that all tag UUIDs exist and belong to the user (or are presets)."""
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
        """Sync TaskTag join table: hard-delete old, insert new."""
        await self.db.execute(
            delete(TaskTag).where(TaskTag.task_uuid == task_uuid)
        )

        for tu in tag_uuids:
            self.db.add(TaskTag(task_uuid=task_uuid, tag_uuid=tu))

    @staticmethod
    def _parse_date(value: str | date_type | None) -> date_type | None:
        """Parse ISO date string safely. Accepts pre-parsed date from Pydantic."""
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
        """Parse ISO datetime string safely."""
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
    ) -> dict[str, Any]:
        """Serialize a Task to the detail API response format (tags as objects)."""
        if tags is None:
            tags = []
        return {
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

    def _task_to_list_out(
        self,
        task: Task,
        tag_uuids: list[str] | None = None,
        total_cl: int = 0,
        completed_cl: int = 0,
    ) -> dict[str, Any]:
        """Serialize a Task to the list API response format (tags as UUIDs)."""
        if tag_uuids is None:
            tag_uuids = []
        return {
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

    # =========================================================================
    # Task CRUD
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
        """Paginated task list with filters."""
        stmt = self._task_base_stmt(user_uuid)

        if since is not None:
            since_dt = self._parse_datetime(since)
            if since_dt:
                stmt = stmt.where(Task.updated_at >= since_dt)

        if completed is not None:
            stmt = stmt.where(Task.completed == completed)

        if q:
            stmt = stmt.where(Task.title.ilike(f"%{q}%"))

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar() or 0

        # Paginate
        stmt = stmt.order_by(Task.sort_order.asc(), Task.created_at.desc())
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        rows = (await self.db.execute(stmt)).scalars().all()

        items = []
        for task in rows:
            # Get tag UUIDs for list view
            tag_stmt = select(TaskTag.tag_uuid).where(
                TaskTag.task_uuid == task.uuid,
            )
            tag_result = await self.db.execute(tag_stmt)
            tag_uuids = [row[0] for row in tag_result.all()]

            total_cl, completed_cl = await self._get_checklist_counts(task.uuid)
            items.append(
                self._task_to_list_out(task, tag_uuids, total_cl, completed_cl)
            )

        return {
            "items": items,
            "meta": {
                "total": total,
                "page": page,
                "pageSize": page_size,
                "hasMore": (page * page_size) < total,
            },
        }

    async def get_task(self, uuid: str, user_uuid: str) -> dict[str, Any]:
        """Get task detail with full tag objects."""
        stmt = self._task_base_stmt(user_uuid).where(Task.uuid == uuid)
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在或已删除", code="TASK_NOT_FOUND")

        tags = await self._get_task_tags(uuid)
        total_cl, completed_cl = await self._get_checklist_counts(uuid)
        return self._task_to_out(task, tags, total_cl, completed_cl)

    async def create_task(
        self, user_uuid: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a new task with optional tags."""
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
        await self._validate_tags(user_uuid, tag_uuids)

        task = Task(
            user_uuid=user_uuid,
            title=title,
            urgency_level=urgency_level,
            importance_level=importance_level,
            due_date=self._parse_date(data.get("dueDate")),
            recurrence=data.get("recurrence"),
            note=data.get("note"),
            sort_order=data.get("sortOrder", 0),
            remind_at=self._parse_datetime(data.get("remindAt")),
            remind_offset_minutes=data.get("remindOffsetMinutes"),
        )

        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        if tag_uuids:
            await self._sync_task_tags(task.uuid, tag_uuids)
            await self.db.flush()

        tags = await self._get_task_tags(task.uuid)
        total_cl, completed_cl = await self._get_checklist_counts(task.uuid)
        return self._task_to_out(task, tags, total_cl, completed_cl)

    async def update_task(
        self, uuid: str, user_uuid: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update task fields (partial)."""
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

        # Tags update
        tag_key = "tags" if "tags" in data else ("tag_uuids" if "tag_uuids" in data else None)
        if tag_key:
            tag_uuids = data[tag_key] or []
            await self._validate_tags(user_uuid, tag_uuids)
            await self._sync_task_tags(uuid, tag_uuids)
            changed = True

        if changed:
            await self.db.flush()
            await self.db.refresh(task)

        tags = await self._get_task_tags(uuid)
        total_cl, completed_cl = await self._get_checklist_counts(uuid)
        return self._task_to_out(task, tags, total_cl, completed_cl)

    async def delete_task(self, uuid: str, user_uuid: str) -> None:
        """Soft-delete a task."""
        stmt = self._task_base_stmt(user_uuid).where(Task.uuid == uuid)
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if task is None:
            raise NotFoundException("任务不存在或已删除", code="TASK_NOT_FOUND")
        task.deleted_at = datetime.utcnow()
        await self.db.flush()

    async def restore_task(
        self, uuid: str, user_uuid: str
    ) -> dict[str, Any]:
        """Restore a soft-deleted task."""
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
        await self.db.refresh(task)

        return {
            "uuid": task.uuid,
            "title": task.title,
            "status": "restored",
            "restoredAt": restored_at.isoformat(),
        }

    # =========================================================================
    # Batch operations
    # =========================================================================

    async def batch_tasks(
        self,
        user_uuid: str,
        action: str,
        task_uuids: list[str],
        idempotency_key: str,
        quadrant: int | None = None,
    ) -> dict[str, Any]:
        """Batch operation with idempotency."""
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

        # Idempotency check via Redis
        redis = get_redis()
        idem_key = build_key("idempotency", idempotency_key)
        cached = await redis.get(idem_key)
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

        # Find matching tasks owned by user
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

        affected = list(found_uuids)
        result: dict[str, Any] = {
            "affected": len(affected),
            "taskUuids": affected,
        }
        if action == "move":
            result["movedToQuadrant"] = quadrant

        if not_found:
            result["notFoundUuids"] = not_found

        # Cache idempotency result (24h)
        await redis.set(
            idem_key, json.dumps(result, default=str), ex=_IDEMPOTENCY_TTL
        )

        return result

    # =========================================================================
    # Checklist
    # =========================================================================

    async def _get_task_or_404(self, task_uuid: str, user_uuid: str) -> Task:
        """Get task by UUID and user, or raise TASK_NOT_FOUND."""
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
        """List checklist items for a task."""
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
        """Create a checklist item."""
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
        await self.db.refresh(item)

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
        """Update a checklist item."""
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
        await self.db.refresh(item)

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
        """Soft-delete a checklist item."""
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
