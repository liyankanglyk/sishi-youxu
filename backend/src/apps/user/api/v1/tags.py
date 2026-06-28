"""Tag CRUD endpoints — Phase 2 implementation.

All endpoints use typed Pydantic request models so Swagger/OpenAPI
docs show complete request body schemas.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.apps.user.schemas.v1.tag import TagCreateRequest, TagUpdateRequest
from src.apps.user.services.tag_service import TagService
from src.core.deps import DbSession, RequiredUser
from src.core.response import ok

router = APIRouter(prefix="/tags", tags=["user-tags"])


def _service(db: DbSession) -> TagService:
    return TagService(db)


@router.get("", summary="获取标签列表", description="获取当前用户的所有标签（含预设标签）")
async def list_tags(current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.list_tags(current["uuid"])
    return ok(result)


@router.post("", status_code=201, summary="创建标签", description="创建自定义标签")
async def create_tag(body: TagCreateRequest, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    result = await svc.create_tag(current["uuid"], body.model_dump())
    await db.commit()
    return ok(result)


@router.patch("/{uuid}", summary="更新标签", description="更新标签名称或颜色（预设标签不可修改）")
async def update_tag(
    uuid: str, body: TagUpdateRequest, current: RequiredUser, db: DbSession
) -> dict:
    svc = _service(db)
    result = await svc.update_tag(uuid, current["uuid"], body.model_dump(exclude_unset=True))
    await db.commit()
    return ok(result)


@router.delete("/{uuid}", summary="删除标签", description="删除自定义标签（预设标签不可删除）")
async def delete_tag(uuid: str, current: RequiredUser, db: DbSession) -> dict:
    svc = _service(db)
    await svc.delete_tag(uuid, current["uuid"])
    await db.commit()
    return ok(None)
