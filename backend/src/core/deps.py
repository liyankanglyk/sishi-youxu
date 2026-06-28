"""通用 FastAPI 依赖：DB session、当前用户、管理员守卫。

Phase 3 实现：

- `get_current_user_optional`：可选鉴权。token 缺失 / 无效 / 用户不存在 → 返回 guest actor
  （保留 Phase 0 行为，不破坏已有路由占位）
- `require_current_user`：强制鉴权。token 缺失或无效 → 抛 401；用户不存在 / 禁用 → 抛 401
- `get_ws_user`：走一次性 ws-ticket 消费（不变）
- `require_admin`：校验角色（不变）

兼容要点：
- token 同时支持 Header `Authorization: Bearer ...` 和 Query `?token=...` /
  `?access_token=...`，兼容微信小程序 ws 场景
- actor dict 直接含 role 字段（从 access_token claims 解析得到），不强制每次查库
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Annotated

from fastapi import Depends, Header, Query, Request
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.exceptions import UnauthorizedException
from src.core.logger import get_logger
from src.core.security import consume_ws_ticket, decode_token, extract_token_from_request
from src.models.user import User, UserStatus

logger = get_logger(__name__)


DbSession = Annotated[AsyncSession, Depends(get_db)]


_GUEST_ACTOR: dict = {
    "uuid": None,
    "role": "guest",
    "authenticated": False,
}


async def _resolve_actor(
    request: Request,
    db: AsyncSession,
    *,
    required: bool,
) -> dict:
    """通用 actor 解析：解 token → 查 user → 返回 dict。

    `required=False` 时：token 缺失 / 无效 / 用户不存在都返回 guest actor。
    `required=True` 时：缺失或无效抛 401；用户存在但状态非 active 抛 401。
    """
    token = extract_token_from_request(request)
    if not token:
        if required:
            raise UnauthorizedException(
                "未提供访问令牌", code="AUTH_TOKEN_MISSING"
            )
        return dict(_GUEST_ACTOR)

    try:
        payload = decode_token(token, expected_type="access")
    except JWTError:
        if required:
            raise UnauthorizedException(
                "token 无效或已过期", code="AUTH_TOKEN_INVALID"
            )
        return dict(_GUEST_ACTOR)

    user_uuid = payload.get("sub")
    role = payload.get("role", "user")
    if not user_uuid:
        if required:
            raise UnauthorizedException(
                "token 缺少 sub", code="AUTH_TOKEN_INVALID"
            )
        return dict(_GUEST_ACTOR)

    # 强制鉴权时才查库（轻量查询，只取 uuid/role/status）
    if required:
        stmt = select(User.uuid, User.role, User.status).where(
            User.uuid == user_uuid,
            User.deleted_at.is_(None),
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            raise UnauthorizedException(
                "用户不存在", code="USER_NOT_FOUND"
            )
        if row.status != UserStatus.active:
            raise UnauthorizedException(
                "账号已被禁用或封禁",
                code="AUTH_USER_DISABLED",
            )

        # 检查是否已被管理员强制登出（Redis 缓存）
        try:
            from src.core.redis import build_key, get_redis

            r = get_redis()
            force_logout_key = build_key("force_logout", row.uuid)
            force_logout_ts = await r.get(force_logout_key)
            if force_logout_ts is not None:
                iat = payload.get("iat", 0)
                if isinstance(iat, datetime):
                    iat = iat.timestamp()
                if float(iat) < float(force_logout_ts):
                    raise UnauthorizedException(
                        "账号已被强制登出，请重新登录",
                        code="AUTH_FORCE_LOGOUT",
                    )
        except UnauthorizedException:
            raise
        except Exception:
            # Redis 不可用时放行，不影响正常业务
            pass

        return {
            "uuid": row.uuid,
            "role": row.role.value if hasattr(row.role, "value") else str(row.role),
            "authenticated": True,
            "jti": payload.get("jti"),
            "raw": payload,
        }

    # 可选鉴权：trust claims，避免对 guest 路由增加 DB 压力
    return {
        "uuid": user_uuid,
        "role": role,
        "authenticated": True,
        "jti": payload.get("jti"),
        "raw": payload,
    }


async def get_current_user_optional(
    request: Request,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """骨架阶段沿用的「可选鉴权」依赖：Phase 3 实现真实解析但保留 guest 行为。"""
    return await _resolve_actor(request, db, required=False)


async def require_current_user(
    request: Request,
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    """强制鉴权：缺 token / 无效 / 用户不存在 / 禁用 → 抛 401。"""
    return await _resolve_actor(request, db, required=True)


CurrentUser = Annotated[dict, Depends(get_current_user_optional)]
RequiredUser = Annotated[dict, Depends(require_current_user)]


async def get_ws_user(
    token: Annotated[str | None, Query(alias="token")] = None,
) -> dict:
    """WebSocket 专用：通过一次性 ticket 解析 user。

    调用后 ticket 立即作废（GETDEL）。
    """
    if not token:
        raise UnauthorizedException("ws ticket 缺失", code="WS_TICKET_MISSING")

    user_uuid = await consume_ws_ticket(token)
    if not user_uuid:
        raise UnauthorizedException("ws ticket 无效或已过期", code="WS_TICKET_INVALID")

    return {"uuid": user_uuid, "role": "user", "authenticated": True}


WsUser = Annotated[dict, Depends(get_ws_user)]


async def require_admin(current: CurrentUser) -> dict:
    """管理员端点的骨架守卫。"""
    if current.get("role") not in {"admin", "super_admin"}:
        raise UnauthorizedException("需要管理员权限", code="AUTH_ADMIN_REQUIRED")
    return current


AdminUser = Annotated[dict, Depends(require_admin)]
RequireAdmin = Annotated[dict, Depends(require_admin)]


__all__ = [
    "DbSession",
    "CurrentUser",
    "RequiredUser",
    "WsUser",
    "AdminUser",
    "RequireAdmin",
    "get_current_user_optional",
    "require_current_user",
    "get_ws_user",
    "require_admin",
]