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
