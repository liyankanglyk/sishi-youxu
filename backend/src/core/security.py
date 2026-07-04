"""安全工具：JWT 签发/解析、ws-ticket、密码哈希。

骨架：仅声明接口 —— 真实认证流程将接入此处。

兼容要点：

- `create_ws_ticket()` / `verify_ws_ticket()` —— 用于 WebSocket 握手时的
  一次性 ticket。微信小程序 `wx.connectSocket` 不支持自定义 Header
  也不支持 Sec-WebSocket-Protocol，客户端必须先调
  `POST /api/v1/auth/ws-ticket` 拿 ticket，再用
  `wx://host/ws/notifications?token=<ticket>` 连接。
- `extract_token_from_request()` 同时支持 `Authorization: Bearer ...` Header
  和 `?token=...` / `?access_token=...` Query 参数。
- 密码哈希用 bcrypt；TokenPair 内 jti 用于服务端撤销。
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
from fastapi import Request
from jose import JWTError, jwt

from src.core.config import settings
from src.core.exceptions import UnauthorizedException
from src.core.redis import build_key, get_redis, getdel


# ---------- 密码哈希 ----------

def hash_password(plain: str) -> str:
    """使用 bcrypt 对明文密码进行哈希。"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码与 bcrypt 哈希是否匹配。"""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------- JWT ----------

TokenKind = Literal["access", "refresh"]


def _now() -> datetime:
    """朴素 UTC —— 与 MySQL DATETIME 列以及 models.base 中的 `_now()` 一致。"""
    return datetime.utcnow()


def _naive_utc_to_ts(dt: datetime) -> int:
    """将朴素 UTC datetime 转换为 Unix 时间戳。

    Naive datetime 的 `.timestamp()` 在非 UTC 时区会被当成本地时间，
    导致 iat/exp 错位 → token 看起来「立刻过期」。
    解决方案：附 timezone.utc 后再取 timestamp。
    """
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def create_access_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> tuple[str, str, datetime]:
    """创建访问令牌，返回 (token, jti, expires_at)。"""
    return _create_token(
        subject,
        kind="access",
        extra_claims=extra_claims,
        expires_delta=timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(
    subject: str,
    *,
    extra_claims: dict[str, Any] | None = None,
    expires_days: int | None = None,
) -> tuple[str, str, datetime]:
    """创建刷新令牌，返回 (token, jti, expires_at)。"""
    return _create_token(
        subject,
        kind="refresh",
        extra_claims=extra_claims,
        expires_delta=timedelta(days=expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def _create_token(
    subject: str,
    *,
    kind: TokenKind,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None,
) -> tuple[str, str, datetime]:
    jti = uuid.uuid4().hex
    now = _now()
    expires_at = now + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "type": kind,
        "iat": _naive_utc_to_ts(now),
        "exp": _naive_utc_to_ts(expires_at),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expires_at


def decode_token(token: str, *, expected_type: TokenKind | None = None) -> dict[str, Any]:
    """解码并校验 JWT，失败时抛出 JWTError。"""
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise JWTError(f"token type mismatch: expected {expected_type}")
    return payload


def decode_token_or_raise(token: str, *, expected_type: TokenKind | None = None) -> dict[str, Any]:
    """解码 JWT；任何失败都抛出 UnauthorizedException。

    在依赖项中使用，避免 JWTError 被冒泡到全局处理器并被当作通用 500。
    映射为带规范错误码的 401，使响应外壳保持一致。
    """
    try:
        return decode_token(token, expected_type=expected_type)
    except JWTError as exc:
        raise UnauthorizedException(
            "token 无效或已过期", code="AUTH_TOKEN_INVALID"
        ) from exc


def extract_token_from_request(request: Request) -> str | None:
    """从 Header 或 Query 中提取 bearer token。

    兼容场景：
    - Web / Capacitor：`Authorization: Bearer <access_token>` 走 Header
    - 微信小程序 ws：`?token=<ticket>` 走 Query（Header 受限）
    - 微信小程序 REST：`Authorization: Bearer <access_token>` 走 Header
      （小程序非 ws 场景 Header 仍然可用）
    """
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if auth:
        parts = auth.split()
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1]:
            return parts[1]

    # 兼容 query string 取 token（ws 场景）
    query_token = request.query_params.get("token") or request.query_params.get("access_token")
    if query_token:
        return query_token

    return None


# ---------- WebSocket ticket（兼容小程序） ----------

def create_ws_ticket(user_uuid: str) -> tuple[str, datetime]:
    """签发一次性 WebSocket ticket。

    返回 (ticket, expires_at)。ticket 存到 Redis（带 TTL），
    ws 握手时再用 `verify_ws_ticket` 校验并立即消费（DEL）。

    为什么不用 JWT 直接当 ticket？
    - 小程序 ws 不支持自定义 Header，必须把凭证放在 URL 里
    - JWT 太长（>200 字符）会撑爆 URL，且无法在握手成功后立即撤销
    - ticket 是一次性的：60s TTL + 单次消费，用完即焚
    """
    ticket = secrets.token_urlsafe(32)
    # 返回 tz-aware UTC datetime，便于客户端跨时区计算
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.WS_TICKET_EXPIRE_SECONDS)
    return ticket, expires_at


async def store_ws_ticket(ticket: str, user_uuid: str) -> None:
    """将 ws ticket 持久化到 Redis，key 为 sishiyouxu:ws:ticket:<ticket>。"""
    redis = get_redis()
    await redis.set(
        build_key("ws:ticket", ticket),
        user_uuid,
        ex=settings.WS_TICKET_EXPIRE_SECONDS,
    )


async def consume_ws_ticket(ticket: str) -> str | None:
    """原子地消费一个 ws ticket；成功返回 user_uuid，否则返回 None。

    GETDEL 保证「校验即作废」——同一 ticket 不能被两个连接复用。
    """
    redis = get_redis()
    key = build_key("ws:ticket", ticket)
    user_uuid = await getdel(redis, key)
    if isinstance(user_uuid, bytes):
        user_uuid = user_uuid.decode("utf-8")
    return user_uuid


# ---------- 登录锁定 ----------

# 锁定阈值
USER_MAX_FAILURES = 5       # 普通用户最多失败 5 次
ADMIN_MAX_FAILURES = 3      # 管理员最多失败 3 次
IP_MAX_FAILURES = 10        # 同一 IP 最多失败 10 次
LOCKOUT_TTL = 900           # 锁定 15 分钟
FAIL_WINDOW_TTL = 900       # 失败计数窗口 15 分钟


async def check_login_locked(identifier: str, *, is_admin: bool = False) -> bool:
    """检查账号是否已被登录锁定。

    优先级：Redis 锁定标记 > Redis 失败计数 > DB locked_until。
    返回 True 表示已锁定，应拒绝登录。
    """
    from src.core.redis import build_key, get_redis

    max_failures = ADMIN_MAX_FAILURES if is_admin else USER_MAX_FAILURES

    try:
        redis = get_redis()
        lock_key = build_key("login_locked", identifier)

        # 1. 先查 Redis 锁定标记（最快）
        if await redis.exists(lock_key):
            return True

        # 2. 查 Redis 失败计数
        fail_key = build_key("login_fail", identifier)
        fail_count_raw = await redis.get(fail_key)
        if fail_count_raw is not None:
            if int(fail_count_raw) >= max_failures:
                # 失败次数已达阈值 → 补写锁定标记
                await redis.set(lock_key, "1", ex=LOCKOUT_TTL)
                return True
            return False
    except Exception:
        pass  # Redis 不可用 → 回退到 DB

    # 3. Redis 不可用时查 DB
    return await _check_db_locked(identifier)


async def _check_db_locked(identifier: str) -> bool:
    """从数据库检查用户的锁定状态（Redis 不可用时的回退）。"""
    from datetime import datetime as dt

    from sqlalchemy import select

    from src.core.database import AsyncSessionLocal
    from src.models.auth import AuthIdentity, AuthProvider

    try:
        async with AsyncSessionLocal() as db:
            # 先通过 identifier 找到 user_uuid
            stmt = select(AuthIdentity.user_uuid).where(
                AuthIdentity.provider == AuthProvider.password,
                AuthIdentity.provider_uid == identifier,
                AuthIdentity.deleted_at.is_(None),
            )
            row = (await db.execute(stmt)).first()
            if row is None:
                return False

            from src.models.user import User
            user_stmt = select(User.locked_until).where(
                User.uuid == row.user_uuid,
                User.deleted_at.is_(None),
            )
            user_row = (await db.execute(user_stmt)).first()
            if user_row is None or user_row.locked_until is None:
                return False
            return user_row.locked_until > dt.utcnow()
    except Exception:
        return False


async def record_login_failure(identifier: str, *, is_admin: bool = False, ip: str | None = None) -> dict:
    """记录一次登录失败。

    返回 {"locked": bool, "remaining": int}，
    其中 remaining 为剩余尝试次数（0 表示已锁定）。
    同时更新 DB 中的 failed_login_attempts 和 locked_until。
    """
    from src.core.redis import build_key, get_redis

    max_failures = ADMIN_MAX_FAILURES if is_admin else USER_MAX_FAILURES
    locked = False

    try:
        redis = get_redis()
        fail_key = build_key("login_fail", identifier)
        # INCR + EXPIRE 原子操作
        count = await redis.incr(fail_key)
        await redis.expire(fail_key, FAIL_WINDOW_TTL)

        if count >= max_failures:
            lock_key = build_key("login_locked", identifier)
            await redis.set(lock_key, "1", ex=LOCKOUT_TTL)
            locked = True

        remaining = max(0, max_failures - count)
    except Exception:
        # Redis 不可用 → 回退到 DB 计数
        remaining = 0
        locked = await _record_db_failure(identifier, max_failures)

    # IP 维度计数
    if ip:
        try:
            redis2 = get_redis()
            ip_key = build_key("login_fail_ip", ip)
            await redis2.incr(ip_key)
            await redis2.expire(ip_key, FAIL_WINDOW_TTL)
        except Exception:
            pass

    return {"locked": locked, "remaining": remaining}


async def _record_db_failure(identifier: str, max_failures: int) -> bool:
    """在数据库中更新失败计数（Redis 不可用时的回退）。"""
    from datetime import datetime as dt, timedelta

    from sqlalchemy import select, update

    from src.core.database import AsyncSessionLocal
    from src.models.auth import AuthIdentity, AuthProvider
    from src.models.user import User

    try:
        async with AsyncSessionLocal() as db:
            stmt = select(AuthIdentity.user_uuid).where(
                AuthIdentity.provider == AuthProvider.password,
                AuthIdentity.provider_uid == identifier,
                AuthIdentity.deleted_at.is_(None),
            )
            row = (await db.execute(stmt)).first()
            if row is None:
                return False

            user_stmt = select(User.failed_login_attempts).where(
                User.uuid == row.user_uuid,
                User.deleted_at.is_(None),
            )
            user_row = (await db.execute(user_stmt)).first()
            if user_row is None:
                return False

            new_count = (user_row.failed_login_attempts or 0) + 1
            locked = new_count >= max_failures

            values = {"failed_login_attempts": new_count}
            if locked:
                values["locked_until"] = dt.utcnow() + timedelta(seconds=LOCKOUT_TTL)

            await db.execute(
                update(User).where(User.uuid == row.user_uuid).values(**values)
            )
            await db.commit()
            return locked
    except Exception:
        return False


async def reset_login_failures(identifier: str) -> None:
    """登录成功后清除该账号的失败计数和锁定标记。"""
    from src.core.redis import build_key, get_redis

    try:
        redis = get_redis()
        await redis.delete(
            build_key("login_fail", identifier),
            build_key("login_locked", identifier),
        )
    except Exception:
        pass

    # 同时清除 DB 中的计数
    await _reset_db_failures(identifier)


async def _reset_db_failures(identifier: str) -> None:
    """清除数据库中的失败计数（Redis 不可用时的回退）。"""
    from sqlalchemy import select, update

    from src.core.database import AsyncSessionLocal
    from src.models.auth import AuthIdentity, AuthProvider
    from src.models.user import User

    try:
        async with AsyncSessionLocal() as db:
            stmt = select(AuthIdentity.user_uuid).where(
                AuthIdentity.provider == AuthProvider.password,
                AuthIdentity.provider_uid == identifier,
                AuthIdentity.deleted_at.is_(None),
            )
            row = (await db.execute(stmt)).first()
            if row is None:
                return

            await db.execute(
                update(User)
                .where(User.uuid == row.user_uuid)
                .values(failed_login_attempts=0, locked_until=None)
            )
            await db.commit()
    except Exception:
        pass


async def check_ip_locked(ip: str) -> bool:
    """检查 IP 是否因过多失败尝试被锁定。"""
    from src.core.redis import build_key, get_redis

    try:
        redis = get_redis()
        ip_key = build_key("login_fail_ip", ip)
        count_raw = await redis.get(ip_key)
        if count_raw is not None and int(count_raw) >= IP_MAX_FAILURES:
            return True
    except Exception:
        pass
    return False


# ---------- 其他 ----------

def sha256_hex(value: str) -> str:
    """对字符串计算 SHA-256，返回小写十六进制。"""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_uuid() -> str:
    """生成一个新的 UUID4 字符串。"""
    return str(uuid.uuid4())


def random_token(length: int = 32) -> str:
    """生成 URL 安全的随机 token（如验证码/口令）。"""
    return secrets.token_urlsafe(length)
