"""Async Redis client + key-builder helpers.

Skeleton: a single shared client + a `sishiyouxu:` prefix applied automatically.
"""
from __future__ import annotations

import redis.asyncio as redis_async

from src.core.config import settings

_redis: redis_async.Redis | None = None


def get_redis() -> redis_async.Redis:
    """Return the shared async Redis client (lazy-initialized).

    兼容老版本 Redis (< 6)：禁用 RESP3 协议（HELLO 3 命令）。
    """
    global _redis
    if _redis is None:
        _redis = redis_async.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            protocol=2,  # RESP2；老 Redis（< 6）不支持 HELLO 3
        )
    return _redis


async def close_redis() -> None:
    """Close the Redis client on shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def build_key(*parts: str) -> str:
    """Build a namespaced Redis key, e.g. build_key('rate:login', ip) -> 'sishiyouxu:rate:login:1.2.3.4'."""
    return ":".join((settings.REDIS_KEY_PREFIX, *parts))


# ── IP 黑名单缓存 ──
IP_BLACKLIST_CACHE_KEY = "sishiyouxu:ip_blacklist:cache"
IP_BLACKLIST_CACHE_TTL = 300  # 5 分钟


async def invalidate_ip_blacklist_cache(client: redis_async.Redis | None = None) -> None:
    """清除 IP 黑名单缓存（管理员增删条目后调用）。"""
    r = client or get_redis()
    await r.delete(IP_BLACKLIST_CACHE_KEY)


async def getdel(client: redis_async.Redis, key: str) -> str | None:
    """Atomically GET a key then DEL it.

    Compatible with Redis < 6.2 (which lacks the GETDEL command).
    Uses a Lua script for atomicity.
    Returns the value, or None if key did not exist.
    """
    lua = (
        "local val = redis.call('GET', KEYS[1]) "
        "if val then redis.call('DEL', KEYS[1]) end "
        "return val"
    )
    raw = await client.eval(lua, 1, key)
    return raw  # type: ignore[return-value]