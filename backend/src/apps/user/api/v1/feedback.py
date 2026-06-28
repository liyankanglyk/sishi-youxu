"""Feedback endpoints — Phase 2 implementation.

Implemented:
- POST /feedback — submit feedback (anonymous or authenticated)
- GET /feedback — list my feedback (requires auth)
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from src.apps.user.schemas.v1.feedback import FeedbackCreateRequest
from src.core.deps import CurrentUser, DbSession, RequiredUser
from src.core.exceptions import ValidationException
from src.core.response import ok
from src.models.admin import Feedback, FeedbackStatus

router = APIRouter(prefix="/feedback", tags=["user-feedback"])


@router.post("", status_code=201, summary="提交反馈", description="提交用户反馈（可匿名）")
async def create_feedback(body: FeedbackCreateRequest, current: CurrentUser, db: DbSession) -> dict:
    content = body.content.strip()
    if not content:
        raise ValidationException(
            "反馈内容不能为空",
            code="VALIDATION_ERROR",
            detail={"content": "反馈内容不能为空"},
        )

    contact = body.contact.strip() if body.contact else None

    feedback = Feedback(
        user_uuid=current.get("uuid") if current.get("authenticated") else None,
        content=content,
        contact=contact,
        status=FeedbackStatus.pending,
    )
    db.add(feedback)
    await db.flush()
    await db.commit()
    await db.refresh(feedback)

    return ok({
        "uuid": feedback.uuid,
        "content": feedback.content,
        "contact": feedback.contact,
        "status": feedback.status.value if hasattr(feedback.status, "value") else str(feedback.status),
        "createdAt": feedback.created_at.isoformat() if feedback.created_at else None,
    })


@router.get("", summary="查询我的反馈", description="查询当前用户提交的反馈列表")
async def list_feedback(
    current: RequiredUser,
    db: DbSession,
    page: int = Query(default=1, ge=1, description="页码"),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize", description="每页数量"),
) -> dict:
    stmt = select(Feedback).where(
        Feedback.user_uuid == current["uuid"],
        Feedback.deleted_at.is_(None),
    )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = stmt.order_by(Feedback.created_at.desc())
    stmt = stmt.limit(pageSize).offset((page - 1) * pageSize)
    rows = (await db.execute(stmt)).scalars().all()

    items = [
        {
            "uuid": f.uuid,
            "content": f.content,
            "contact": f.contact,
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "createdAt": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
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
