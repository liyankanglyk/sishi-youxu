"""Redis 缓存辅助层。

提供统一的缓存读写、批量失效，供 service 层使用。

Key 规范：sishiyouxu:cache:{域}:{标识}
**所有 key 强制设置 TTL**，防止冷数据堆积和内存泄漏。

用法示例：
    # 读取
    cached = await cache_get("tags", user_uuid)
    if cached is not None:
        return cached
    # ... 查 DB ...
    await cache_set("tags", user_uuid, value=result, ttl=TAG_LIST_TTL)

    # 写入（ttl 关键字参数强制必填）
    await cache_set("tasks", user_uuid, value=data, ttl=30)

    # 失效
    await cache_invalidate_user("tags", user_uuid)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.core.redis import build_key, get_redis

# ── TTL 常量（秒）— 所有缓存 key 必须设置过期时间 ──
TAG_LIST_TTL = 300        # 标签列表：5 分钟
TASK_LIST_TTL = 30         # 任务列表：30 秒
TASK_DETAIL_TTL = 60       # 任务详情：1 分钟
UNREAD_COUNT_TTL = 15      # 未读计数：15 秒（前端每 30s 轮询）
USER_PROFILE_TTL = 300     # 用户资料：5 分钟
NOTIF_LIST_TTL = 30        # 通知列表：30 秒


def _make_cache_key(domain: str, *parts: str) -> str:
    """构造缓存 key。对 parts 中过长内容自动 hash 截断。"""
    safe_parts: list[str] = []
    for p in parts:
        if len(p) > 80:
            p = hashlib.md5(p.encode()).hexdigest()[:16]
        safe_parts.append(p)
    return build_key("cache", domain, *safe_parts)


async def cache_get(domain: str, *parts: str) -> Any | None:
    """从 Redis 读取缓存值（JSON 反序列化）。不存在返回 None。"""
    try:
        redis = get_redis()
        key = _make_cache_key(domain, *parts)
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


async def cache_set(domain: str, *parts: str, value: Any, ttl: int) -> None:
    """将值写入 Redis 缓存并设置过期时间。

    Args:
        domain: 缓存域（如 "tags"、"tasks"）
        *parts: key 组成部分（如 user_uuid）
        value: 要缓存的值（会被 JSON 序列化）
        ttl: **必填** — 过期时间（秒），防止 key 永不过期
    """
    try:
        redis = get_redis()
        key = _make_cache_key(domain, *parts)
        await redis.set(key, json.dumps(value, default=str), ex=ttl)
    except Exception:
        pass  # 缓存写入失败不影响主流程


async def cache_delete(domain: str, *parts: str) -> None:
    """删除单条缓存。"""
    try:
        redis = get_redis()
        key = _make_cache_key(domain, *parts)
        await redis.delete(key)
    except Exception:
        pass


async def cache_invalidate_user(domain: str, user_uuid: str) -> None:
    """删除某用户在某域下的所有缓存。

    同时删除精确 key（如 ``cache_get("unread", user_uuid)`` 对应的 key）
    和通配 key（如 ``cache_get("tasks", user_uuid, filter_hash)``）。

    使用 SCAN 避免 KEYS 命令阻塞 Redis。
    """
    try:
        redis = get_redis()
        # 1. 删除精确 key（无额外 parts 的缓存）
        exact_key = _make_cache_key(domain, user_uuid)
        await redis.delete(exact_key)

        # 2. 使用 SCAN 删除带额外 parts 的缓存 key
        pattern = _make_cache_key(domain, user_uuid, "*")
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match=pattern, count=50)
            if keys:
                await redis.delete(*keys)
            if cursor == 0:
                break
    except Exception:
        pass


# ── 用户维度缓存失效快捷方法 ──

async def invalidate_user_tags(user_uuid: str) -> None:
    """失效用户标签缓存。"""
    await cache_invalidate_user("tags", user_uuid)


async def invalidate_user_tasks(user_uuid: str) -> None:
    """失效用户任务列表/详情缓存。"""
    await cache_invalidate_user("tasks", user_uuid)


async def invalidate_user_notifications(user_uuid: str) -> None:
    """失效用户通知相关缓存（列表 + 未读计数）。"""
    await cache_invalidate_user("notif", user_uuid)
    await cache_invalidate_user("unread", user_uuid)


async def invalidate_user_profile(user_uuid: str) -> None:
    """失效用户资料缓存。"""
    await cache_invalidate_user("user", user_uuid)


__all__ = [
    "cache_get",
    "cache_set",
    "cache_delete",
    "cache_invalidate_user",
    "invalidate_user_tags",
    "invalidate_user_tasks",
    "invalidate_user_notifications",
    "invalidate_user_profile",
    "TAG_LIST_TTL",
    "TASK_LIST_TTL",
    "TASK_DETAIL_TTL",
    "UNREAD_COUNT_TTL",
    "USER_PROFILE_TTL",
    "NOTIF_LIST_TTL",
]
