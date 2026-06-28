"""Security utilities: JWT issuing/parsing, ws-ticket, password hashing.

Skeleton: surface only — real auth flows will plug in here.

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


# ---------- Password hashing ----------

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ---------- JWT ----------

TokenKind = Literal["access", "refresh"]


def _now() -> datetime:
    """Naive UTC — matches MySQL DATETIME columns and `_now()` in models.base."""
    return datetime.utcnow()


def _naive_utc_to_ts(dt: datetime) -> int:
    """Convert naive UTC datetime to Unix timestamp.

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
    """Create an access token. Returns (token, jti, expires_at)."""
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
    """Create a refresh token. Returns (token, jti, expires_at)."""
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
    """Decode and validate a JWT. Raises JWTError on failure."""
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    if expected_type and payload.get("type") != expected_type:
        raise JWTError(f"token type mismatch: expected {expected_type}")
    return payload


def decode_token_or_raise(token: str, *, expected_type: TokenKind | None = None) -> dict[str, Any]:
    """Decode a JWT; raise UnauthorizedException on any failure.

    Used by deps where JWTError would otherwise bubble up to the global handler
    as a generic 500. Mapping to a 401 with the spec'd error code keeps the
    response envelope consistent.
    """
    try:
        return decode_token(token, expected_type=expected_type)
    except JWTError as exc:
        raise UnauthorizedException(
            "token 无效或已过期", code="AUTH_TOKEN_INVALID"
        ) from exc


def extract_token_from_request(request: Request) -> str | None:
    """Extract a bearer token from either Header or Query.

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


# ---------- WebSocket ticket (compatible with mini-program) ----------

def create_ws_ticket(user_uuid: str) -> tuple[str, datetime]:
    """Issue a one-time WebSocket ticket.

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
    """Persist a ws ticket in Redis under sishiyouxu:ws:ticket:<ticket>."""
    redis = get_redis()
    await redis.set(
        build_key("ws:ticket", ticket),
        user_uuid,
        ex=settings.WS_TICKET_EXPIRE_SECONDS,
    )


async def consume_ws_ticket(ticket: str) -> str | None:
    """Atomically consume a ws ticket; return user_uuid on success, None otherwise.

    GETDEL 保证「校验即作废」——同一 ticket 不能被两个连接复用。
    """
    redis = get_redis()
    key = build_key("ws:ticket", ticket)
    user_uuid = await getdel(redis, key)
    if isinstance(user_uuid, bytes):
        user_uuid = user_uuid.decode("utf-8")
    return user_uuid


# ---------- Misc ----------

def sha256_hex(value: str) -> str:
    """SHA-256 of a string, returned as lowercase hex."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def random_token(length: int = 32) -> str:
    """Generate a URL-safe random token (e.g. captcha/codes)."""
    return secrets.token_urlsafe(length)
