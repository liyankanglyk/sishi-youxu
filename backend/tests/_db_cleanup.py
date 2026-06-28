"""测试共用的清理工具。

集中处理测试产生的 User / AuthIdentity / RefreshToken / 头像本地文件清理，
供 conftest.py 与各测试模块复用，避免测试数据污染 dev DB。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

# tests 目录的父目录 = backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent


def purge_test_users(user_uuids: list[str]) -> None:
    """硬删除测试期间注册的 User 及其关联数据 + 头像本地文件。

    - 复用 AsyncSessionLocal 直接走 SQLAlchemy，避免污染路由层日志。
    - 删除顺序：RefreshToken → AuthIdentity → User（无 FK 约束但保持语义）。
    - 头像清理遍历 {jpg,jpeg,png,webp} 扩展名（与 UserService.upload_avatar 一致）。
    - 失败仅 print warning，不抛错（DB/FS 不可用时让测试通过优先）。
    """
    if not user_uuids:
        return
    try:
        asyncio.run(_purge_async(user_uuids))
    except Exception as exc:  # noqa: BLE001 — 清理失败不能影响测试结果
        print(f"[test-cleanup] warning: failed to purge users {user_uuids}: {exc}")

    # 头像本地文件（dev 模式写入 backend/avatars/）
    avatars_dir = BACKEND_ROOT / "avatars"
    if avatars_dir.is_dir():
        for uuid in user_uuids:
            for ext in (".jpg", ".jpeg", ".png", ".webp"):
                p = avatars_dir / f"{uuid}{ext}"
                if p.exists():
                    try:
                        p.unlink()
                    except OSError as exc:
                        print(f"[test-cleanup] warning: failed to remove avatar {p}: {exc}")


async def _purge_async(user_uuids: list[str]) -> None:
    from sqlalchemy import delete

    from src.core.database import AsyncSessionLocal
    from src.models import AuthIdentity, RefreshToken, User

    async with AsyncSessionLocal() as session:
        # 子表先删（尽管 DB 没加 FK 约束，仍按语义顺序清理）
        await session.execute(
            delete(RefreshToken).where(RefreshToken.user_uuid.in_(user_uuids))
        )
        await session.execute(
            delete(AuthIdentity).where(AuthIdentity.user_uuid.in_(user_uuids))
        )
        await session.execute(
            delete(User).where(User.uuid.in_(user_uuids))
        )
        await session.commit()
