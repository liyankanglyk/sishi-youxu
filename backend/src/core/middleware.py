"""应用中间件：CORS、请求 ID、客户端平台识别、IP 黑名单、统一错误处理。

骨架：在 src.main 中挂载；处理器仅做最小工作，使框架在 MySQL/Redis
不可用时仍可启动。

平台识别：`X-Client-Platform` 取值约定为 `web` / `capacitor` / `miniapp`，
落到 `request.state.client_platform`，便于审计日志、限流策略、Sensitive-Word
过滤等按平台差异化处理。
"""
from __future__ import annotations

import ipaddress
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings
from src.core.exceptions import BusinessException
from src.core.logger import get_logger
from src.core.response import fail

logger = get_logger(__name__)

_ALLOWED_PLATFORMS = {"web", "capacitor", "miniapp", "unknown"}

# 跳过 IP 黑名单检查的路径前缀
_IP_BLACKLIST_SKIP_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/static/",
    "/redoc",
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求/响应附加唯一的 `X-Request-ID`。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id

        # 平台识别：Header > User-Agent 启发式 > unknown
        platform = (request.headers.get("X-Client-Platform") or "").lower().strip()
        if platform not in _ALLOWED_PLATFORMS:
            ua = (request.headers.get("User-Agent") or "").lower()
            if "micromessenger" in ua:
                platform = "miniapp"
            elif "capacitor" in ua:
                platform = "capacitor"
            elif ua:
                platform = "web"
            else:
                platform = "unknown"
        request.state.client_platform = platform

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Elapsed-ms"] = f"{elapsed_ms:.2f}"
        response.headers["X-Client-Platform"] = platform
        return response


def _get_client_ip(request: Request) -> str:
    """获取客户端真实 IP，依次检查 X-Forwarded-For / X-Real-IP / request.client."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri.strip()
    if request.client:
        return request.client.host
    return "unknown"


class IpBlacklistMiddleware(BaseHTTPMiddleware):
    """检查请求 IP 是否在黑名单中。

    - 先查 Redis 缓存，命中则直接判定
    - 未命中则查 DB，结果缓存 TTL=300s
    - 支持精确 IP 和 CIDR 网段
    - 已过期条目自动跳过
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        for prefix in _IP_BLACKLIST_SKIP_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        client_ip = _get_client_ip(request)
        if client_ip in ("127.0.0.1", "::1", "unknown"):
            return await call_next(request)

        is_blocked = await self._check_ip(client_ip)
        if is_blocked:
            logger.warning("blocked IP %s on path %s", client_ip, path)
            return JSONResponse(
                status_code=403,
                content=fail("IP_BLOCKED", "您的 IP 已被限制访问", {}),
            )

        return await call_next(request)

    async def _check_ip(self, client_ip: str) -> bool:
        """检查 IP 是否在黑名单中，优先使用 Redis 缓存。"""
        from src.core.redis import IP_BLACKLIST_CACHE_KEY, get_redis

        try:
            r = get_redis()
            cache_key = f"{IP_BLACKLIST_CACHE_KEY}:checked:{client_ip}"
            cached = await r.get(cache_key)
            if cached is not None:
                return cached == "1"
        except Exception:
            return await self._check_ip_db(client_ip)

        blocked = await self._check_ip_db(client_ip)
        try:
            await r.setex(cache_key, 60, "1" if blocked else "0")
        except Exception:
            pass
        return blocked

    async def _check_ip_db(self, client_ip: str) -> bool:
        """从数据库查询 IP 是否在黑名单中（含 CIDR 匹配）。"""
        try:
            from src.core.database import AsyncSessionLocal
            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                from src.models.admin import IpBlacklist

                stmt = select(IpBlacklist).where(
                    IpBlacklist.ip_address == client_ip
                )
                result = await db.execute(stmt)
                exact = result.scalars().all()

                now = datetime.now(timezone.utc)
                for entry in exact:
                    if entry.expires_at and entry.expires_at.replace(tzinfo=timezone.utc) < now:
                        continue
                    return True

                # CIDR 范围匹配：拉取包含 '/' 的条目
                cidr_stmt = select(IpBlacklist).where(
                    IpBlacklist.ip_address.contains("/")
                )
                cidr_result = await db.execute(cidr_stmt)
                cidr_entries = cidr_result.scalars().all()

                try:
                    parsed_ip = ipaddress.ip_address(client_ip)
                except ValueError:
                    return False

                for entry in cidr_entries:
                    if entry.expires_at and entry.expires_at.replace(tzinfo=timezone.utc) < now:
                        continue
                    try:
                        network = ipaddress.ip_network(entry.ip_address, strict=False)
                        if parsed_ip in network:
                            return True
                    except ValueError:
                        continue

                return False
        except Exception:
            return False


class BusinessExceptionMiddleware(BaseHTTPMiddleware):
    """将 BusinessException 翻译为规范定义的失败响应外壳。"""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        try:
            return await call_next(request)
        except BusinessException as exc:
            logger.warning(
                "business exception: %s (%s)", exc.code, exc.message
            )
            return JSONResponse(
                status_code=exc.http_status,
                content=fail(exc.code, exc.message, exc.detail),
            )
        except Exception as exc:  # pragma: no cover - 兜底处理器
            logger.exception("unhandled exception: %s", exc)
            detail = {"hint": str(exc)} if settings.DEBUG else {}
            return JSONResponse(
                status_code=500,
                content=fail("INTERNAL_ERROR", "服务器内部错误", detail),
            )


def install_middlewares(app: FastAPI) -> None:
    """在 FastAPI app 上注册所有中间件。

    顺序很重要：最外层中间件最先注册。
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-Elapsed-ms",
            "X-Client-Platform",
        ],
    )
    app.add_middleware(IpBlacklistMiddleware)
    app.add_middleware(BusinessExceptionMiddleware)
    app.add_middleware(RequestIDMiddleware)
