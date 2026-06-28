"""通知相关端点 —— Phase 2 实现。

已实现的功能：
- GET /notifications — 分页列表，支持 isRead 筛选
- GET /notifications/unread-count — 未读数量
- PATCH /notifications/{uuid}/read — 标记单条为已读
- POST /notifications/read-all — 全部标记为已读
- DELETE /notifications/{uuid} — 删除通知
"""

from __future__ import annotations

from datetime import datetime, date

from fastapi import APIRouter, Query
from sqlalchemy import func, select, update

from src.core.deps import DbSession, RequiredUser
from src.core.exceptions import NotFoundException
from src.core.response import ok
from src.models.admin import Announcement, Notification, NotificationKind
from src.models.task import Task

router = APIRouter(prefix="/notifications", tags=["user-notifications"])


async def _sync_all(user_uuid: str, db) -> None:
    """为当前用户生成所有待生成的通知：
    1. 过期/今日到期的任务提醒
    2. 用户尚未查看的系统公告
    """
    today = date.today()
    now = datetime.utcnow()
    changed = False

    # ── 1. Task reminders ──
    overdue_tasks = (
        await db.execute(
            select(Task).where(
                Task.user_uuid == user_uuid,
                Task.completed.is_(False),
                Task.deleted_at.is_(None),
                Task.due_date <= today,
            )
        )
    ).scalars().all()

    if overdue_tasks:
        already_notified = set(
            (
                await db.execute(
                    select(Notification.task_uuid).where(
                        Notification.user_uuid == user_uuid,
                        Notification.kind == NotificationKind.task_reminder,
                        Notification.task_uuid.in_([t.uuid for t in overdue_tasks]),
                        func.date(Notification.created_at) == today,
                    )
                )
            ).scalars().all()
        )

        for task in overdue_tasks:
            if task.uuid in already_notified:
                continue
            is_overdue = task.due_date < today
            db.add(
                Notification(
                    user_uuid=user_uuid,
                    kind=NotificationKind.task_reminder,
                    title=f"{'已过期' if is_overdue else '今天到期'}: {task.title}",
                    body=task.note or f"截止日期: {task.due_date.isoformat()}",
                    task_uuid=task.uuid,
                )
            )
            changed = True

    # ── 2. Announcements ──
    active_anns = (
        await db.execute(
            select(Announcement).where(
                Announcement.deleted_at.is_(None),
                Announcement.is_active.is_(True),
            )
        )
    ).scalars().all()

    if active_anns:
        ann_titles = [a.title for a in active_anns]
        existing_titles = set(
            (
                await db.execute(
                    select(Notification.title).where(
                        Notification.user_uuid == user_uuid,
                        Notification.kind == NotificationKind.system_announcement,
                        Notification.title.in_(ann_titles),
                    )
                )
            ).scalars().all()
        )

        for ann in active_anns:
            if ann.title in existing_titles:
                continue
            db.add(
                Notification(
                    user_uuid=user_uuid,
                    kind=NotificationKind.system_announcement,
                    title=ann.title,
                    body=ann.content,
                )
            )
            changed = True

    if changed:
        await db.commit()


# =============================================================================
# 列表
# =============================================================================


@router.get("", summary="获取通知列表", description="分页查询当前用户的通知列表")
async def list_notifications(
    current: RequiredUser,
    db: DbSession,
    isRead: bool | None = Query(default=None, alias="isRead", description="筛选已读/未读"),
    page: int = Query(default=1, ge=1, description="页码"),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
) -> dict:
    await _sync_all(current["uuid"], db)

    stmt = select(Notification).where(
        Notification.user_uuid == current["uuid"],
        Notification.deleted_at.is_(None),
    )

    if isRead is not None:
        stmt = stmt.where(Notification.is_read == isRead)

    # 计数
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # 分页
    stmt = stmt.order_by(Notification.created_at.desc())
    stmt = stmt.limit(pageSize).offset((page - 1) * pageSize)
    rows = (await db.execute(stmt)).scalars().all()

    items = [
        {
            "uuid": n.uuid,
            "kind": n.kind.value if hasattr(n.kind, "value") else str(n.kind),
            "title": n.title,
            "body": n.body,
            "taskUuid": n.task_uuid,
            "isRead": n.is_read,
            "createdAt": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]

    return ok({
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "pageSize": pageSize,
            "hasMore": (page * pageSize) < total,
        },
    })


# =============================================================================
# 未读数量
# =============================================================================


@router.get("/unread-count", summary="通知未读数量", description="获取当前用户未读通知数量")
async def unread_count(current: RequiredUser, db: DbSession) -> dict:
    await _sync_all(current["uuid"], db)
    stmt = select(func.count(Notification.uuid)).where(
        Notification.user_uuid == current["uuid"],
        Notification.is_read.is_(False),
        Notification.deleted_at.is_(None),
    )
    count = (await db.execute(stmt)).scalar() or 0
    return ok({"unreadCount": count})


# =============================================================================
# 标记已读
# =============================================================================


@router.patch("/{uuid}/read", summary="标记已读", description="标记指定通知为已读")
async def mark_read(uuid: str, current: RequiredUser, db: DbSession) -> dict:
    stmt = (
        update(Notification)
        .where(
            Notification.uuid == uuid,
            Notification.user_uuid == current["uuid"],
            Notification.deleted_at.is_(None),
        )
        .values(is_read=True, read_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise NotFoundException("通知不存在", code="NOTIFICATION_NOT_FOUND")
    await db.commit()

    return ok({
        "uuid": uuid,
        "isRead": True,
        "readAt": datetime.utcnow().isoformat(),
    })


# =============================================================================
# 全部标记已读
# =============================================================================


@router.post("/read-all", summary="全部已读", description="标记当前用户所有通知为已读")
async def mark_all_read(current: RequiredUser, db: DbSession) -> dict:
    now = datetime.utcnow()
    stmt = (
        update(Notification)
        .where(
            Notification.user_uuid == current["uuid"],
            Notification.is_read.is_(False),
            Notification.deleted_at.is_(None),
        )
        .values(is_read=True, read_at=now)
    )
    result = await db.execute(stmt)
    await db.commit()

    return ok({"affected": result.rowcount or 0})


# =============================================================================
# 删除
# =============================================================================


@router.delete("/{uuid}", summary="删除通知", description="软删除指定通知")
async def delete_notification(uuid: str, current: RequiredUser, db: DbSession) -> dict:
    stmt = (
        update(Notification)
        .where(
            Notification.uuid == uuid,
            Notification.user_uuid == current["uuid"],
            Notification.deleted_at.is_(None),
        )
        .values(deleted_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise NotFoundException("通知不存在", code="NOTIFICATION_NOT_FOUND")
    await db.commit()

    return ok(None)
