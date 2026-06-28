"""Admin dashboard endpoints — Phase 1 implementation."""
from __future__ import annotations

from fastapi import APIRouter

from src.apps.admin.services.admin_service import AdminService
from src.core.deps import DbSession, RequireAdmin
from src.core.response import ok

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


def _service(db: DbSession) -> AdminService:
    return AdminService(db)


@router.get("/stats", summary="仪表盘统计")
async def dashboard_stats(db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_stats()
    return ok(result)


@router.get("/charts/{metric}", summary="图表数据")
async def dashboard_chart(metric: str, db: DbSession, _admin: RequireAdmin) -> dict:
    svc = _service(db)
    result = await svc.get_chart(metric)
    return ok(result)
