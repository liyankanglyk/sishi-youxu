"""Admin system-config and Phase 4 endpoints.

Sensitive words, IP blacklist, and announcements are now fully implemented (Phase 4).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Form, Query, Request

from src.apps.admin.schemas.v1.admin import (
    AdminConfigUpdateRequest,
    AnnouncementCreateRequest,
    AnnouncementUpdateRequest,
    IpBlacklistCreateRequest,
    SensitiveWordCreateRequest,
    SensitiveWordUpdateRequest,
)
from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


def _service(db: DbSession, request: Request | None = None) -> AdminService:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    return svc


@router.get("", summary="获取系统配置")
async def get_config(db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_config()
    return ok(result)


@router.patch("", summary="更新系统配置")
async def update_config(
    body: AdminConfigUpdateRequest, db: DbSession, admin: RequireAdmin, request: Request
) -> dict:
    svc = _service(db, request)
    result = await svc.update_config(
        body.model_dump(exclude_unset=True), admin_uuid=admin["uuid"]
    )
    await db.commit()
    return ok(result)


# ── Sensitive words (Phase 4: real implementation) ──
sensitive_word_router = APIRouter(prefix="/admin/sensitive-words", tags=["admin-content"])


@sensitive_word_router.get("", summary="敏感词列表")
async def list_sensitive_words(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> dict:
    svc = AdminService(db)
    result = await svc.list_sensitive_words(page=page, page_size=pageSize)
    return ok(result)


@sensitive_word_router.post("", summary="添加敏感词")
async def add_sensitive_word(
    body: SensitiveWordCreateRequest, db: DbSession, _admin: RequireAdmin
) -> dict:
    svc = AdminService(db)
    result = await svc.add_sensitive_word(word=body.word, level=body.level)
    await db.commit()
    return ok(result)


@sensitive_word_router.patch("/{uuid}", summary="更新敏感词")
async def update_sensitive_word(
    uuid: str,
    body: SensitiveWordUpdateRequest,
    db: DbSession,
    _admin: RequireAdmin,
) -> dict:
    svc = AdminService(db)
    result = await svc.update_sensitive_word(uuid, word=body.word, level=body.level)
    await db.commit()
    return ok(result)


@sensitive_word_router.delete("/{uuid}", summary="删除敏感词")
async def delete_sensitive_word(
    uuid: str, db: DbSession, _admin: RequireAdmin
) -> dict:
    svc = AdminService(db)
    await svc.delete_sensitive_word(uuid)
    await db.commit()
    return ok({"deleted": True})


@sensitive_word_router.post("/import", summary="批量导入敏感词")
async def import_sensitive_words(
    db: DbSession,
    _admin: RequireAdmin,
    words: str = Form(default=""),
) -> dict:
    """支持通过 form field 'words' 直接传文本（每行一个敏感词）。"""
    svc = AdminService(db)
    text = words.strip()
    if not text:
        return ok({"imported": 0, "skipped": 0, "message": "未提供导入内容"})
    result = await svc.import_sensitive_words(text)
    await db.commit()
    return ok(result)


# ── Security / IP blacklist (Phase 4: real implementation) ──
security_router = APIRouter(prefix="/admin/security", tags=["admin-security"])


@security_router.get("/ip-blacklist", summary="IP 黑名单列表")
async def list_blacklist(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
) -> dict:
    svc = AdminService(db)
    result = await svc.list_ip_blacklist(page=page, page_size=pageSize)
    return ok(result)


@security_router.post("/ip-blacklist", summary="添加 IP 黑名单")
async def add_blacklist(
    body: IpBlacklistCreateRequest,
    db: DbSession,
    admin: RequireAdmin,
) -> dict:
    svc = AdminService(db)
    expires_at = None
    if body.expiresAt:
        try:
            expires_at = datetime.fromisoformat(body.expiresAt.replace("Z", "+00:00"))
        except ValueError:
            expires_at = datetime.strptime(body.expiresAt, "%Y-%m-%d %H:%M:%S")
    result = await svc.add_ip_blacklist(
        ip_address=body.ipAddress,
        reason=body.reason,
        created_by=admin["uuid"],
        expires_at=expires_at,
    )
    await db.commit()
    from src.core.redis import get_redis, invalidate_ip_blacklist_cache
    await invalidate_ip_blacklist_cache(get_redis())
    return ok(result)


@security_router.delete("/ip-blacklist/{uuid}", summary="移除 IP 黑名单")
async def remove_blacklist(
    uuid: str,
    db: DbSession,
    _admin: RequireAdmin,
) -> dict:
    svc = AdminService(db)
    await svc.delete_ip_blacklist(uuid)
    await db.commit()
    from src.core.redis import get_redis, invalidate_ip_blacklist_cache
    await invalidate_ip_blacklist_cache(get_redis())
    return ok({"deleted": True})


# ── Announcements (Phase 4: real implementation) ──
announcement_router = APIRouter(prefix="/admin/announcements", tags=["admin-announcements"])


@announcement_router.get("", summary="公告列表")
async def list_announcements(
    db: DbSession,
    _admin: RequireAdmin,
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    type: str | None = Query(default=None),
) -> dict:
    svc = AdminService(db)
    result = await svc.list_announcements(page=page, page_size=pageSize, type_filter=type)
    return ok(result)


@announcement_router.post("", summary="创建公告")
async def create_announcement(
    body: AnnouncementCreateRequest,
    db: DbSession,
    admin: RequireAdmin,
    request: Request,
) -> dict:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    start_time = None
    end_time = None
    if body.startTime:
        try:
            start_time = datetime.fromisoformat(body.startTime.replace("Z", "+00:00"))
        except ValueError:
            start_time = datetime.strptime(body.startTime, "%Y-%m-%d %H:%M:%S")
    if body.endTime:
        try:
            end_time = datetime.fromisoformat(body.endTime.replace("Z", "+00:00"))
        except ValueError:
            end_time = datetime.strptime(body.endTime, "%Y-%m-%d %H:%M:%S")

    result = await svc.create_announcement(
        title=body.title,
        content=body.content,
        announcement_type=body.type,
        is_pinned=body.isPinned,
        is_active=body.isActive,
        start_time=start_time,
        end_time=end_time,
        created_by=admin["uuid"],
    )
    await db.commit()
    return ok(result)


@announcement_router.patch("/{uuid}", summary="更新公告")
async def update_announcement(
    uuid: str,
    body: AnnouncementUpdateRequest,
    db: DbSession,
    admin: RequireAdmin,
    request: Request,
) -> dict:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    start_time = None
    end_time = None
    if body.startTime:
        try:
            start_time = datetime.fromisoformat(body.startTime.replace("Z", "+00:00"))
        except ValueError:
            start_time = datetime.strptime(body.startTime, "%Y-%m-%d %H:%M:%S")
    if body.endTime:
        try:
            end_time = datetime.fromisoformat(body.endTime.replace("Z", "+00:00"))
        except ValueError:
            end_time = datetime.strptime(body.endTime, "%Y-%m-%d %H:%M:%S")

    result = await svc.update_announcement(
        uuid=uuid,
        title=body.title,
        content=body.content,
        announcement_type=body.type,
        is_pinned=body.isPinned,
        is_active=body.isActive,
        start_time=start_time,
        end_time=end_time,
        admin_uuid=admin["uuid"],
    )
    await db.commit()
    return ok(result)


@announcement_router.delete("/{uuid}", summary="删除公告")
async def delete_announcement(
    uuid: str,
    db: DbSession,
    admin: RequireAdmin,
    request: Request,
) -> dict:
    svc = AdminService(db)
    if request:
        svc._request_ip = request.client.host if request.client else None
        svc._request_ua = request.headers.get("User-Agent")
    await svc.delete_announcement(uuid, admin_uuid=admin["uuid"])
    await db.commit()
    return ok({"deleted": True})
