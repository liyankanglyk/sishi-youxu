"""User authentication service — Phase 3 implementation.

Phase 0 仅做骨架占位；Phase 3 实现：

- 多 Provider 登录（password / phone_sms / email_code / wechat）
- refresh-token 旋转（refresh 时撤销旧 jti，重复使用触发吊销）
- ws-ticket 签发
- 图形验证码 / 短信验证码 / 邮箱验证码（mock 模式：答案/验证码写入 Redis）
- 密码重置（mock：reset_token 写 Redis）

设计要点：

- 所有写库用 SQLAlchemy 2.0 async session（`flush`/`refresh` 由路由 commit）
- 业务异常统一抛 `BusinessException` 子类，由 `BusinessExceptionMiddleware` 翻译
- 验证码类（sms / email / captcha）走 Redis：key = `sishiyouxu:<功能>:<标识>`，
  TTL 见 `settings`
"""
from __future__ import annotations

import hashlib
import secrets
import uuid as _uuid_lib
from datetime import datetime, timedelta
from typing import Any, Literal

from jose import JWTError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import (
    BusinessException,
    ConflictException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from src.core.logger import get_logger
from src.core.redis import build_key, get_redis, getdel
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    sha256_hex,
    store_ws_ticket,
    verify_password,
)
from src.models.auth import AuthIdentity, AuthProvider, RefreshToken
from src.models.admin import LoginLog, LoginStatus
from src.models.user import User, UserRole, UserStatus
from src.utils.captcha import generate_captcha

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 错误码（spec 命名：大写下划线）
# ---------------------------------------------------------------------------
class AuthErrorCode:
    INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    REFRESH_TOKEN_INVALID = "AUTH_REFRESH_TOKEN_INVALID"
    CODE_INVALID = "AUTH_CODE_INVALID"
    CODE_EXPIRED = "AUTH_CODE_EXPIRED"
    CAPTCHA_INVALID = "AUTH_CAPTCHA_INVALID"
    CAPTCHA_EXPIRED = "AUTH_CAPTCHA_EXPIRED"
    PROVIDER_ALREADY_LINKED = "AUTH_PROVIDER_ALREADY_LINKED"
    PROVIDER_NOT_LINKED = "AUTH_PROVIDER_NOT_LINKED"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    USER_ALREADY_EXISTS = "USER_ALREADY_EXISTS"
    RESET_TOKEN_INVALID = "AUTH_RESET_TOKEN_INVALID"
    VALIDATION_ERROR = "VALIDATION_ERROR"


# Redis key TTLs（秒）
_CAPTCHA_TTL = 300          # 5 分钟
_SMS_CODE_TTL = 300         # 5 分钟
_EMAIL_CODE_TTL = 600       # 10 分钟
_RESET_TOKEN_TTL = 1800     # 30 分钟
_SMS_RATE_LIMIT_TTL = 60    # 同号 60s 内只能发一次
_LOGIN_FAIL_TTL = 900       # 失败计数器 15 分钟


class AuthService:
    """聚合用户端所有认证相关业务。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # Set by route layer before calling login/register/wechat_login
        self._request_ip: str | None = None
        self._request_ua: str | None = None

    # =======================================================================
    # Token 辅助
    # =======================================================================

    async def _issue_token_pair(self, user: User) -> dict[str, Any]:
        """签发 access + refresh，并落库 `sishiyouxu_refresh_token`。"""
        # 把 role 注入 access token claims，方便 deps 直接读，避免再次查表
        extra = {"role": user.role.value if hasattr(user.role, "value") else str(user.role)}
        access_token, _, access_exp = create_access_token(
            user.uuid, extra_claims=extra
        )
        refresh_token, jti, refresh_exp = create_refresh_token(user.uuid)

        # token_hash：存 SHA-256，校验时只比较 hash，不存明文
        self.db.add(
            RefreshToken(
                user_uuid=user.uuid,
                jti=jti,
                token_hash=sha256_hex(refresh_token),
                expires_at=refresh_exp,
            )
        )
        await self.db.flush()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": int((access_exp - datetime.utcnow()).total_seconds()),
        }

    async def _resolve_refresh_token(self, token: str) -> tuple[RefreshToken, dict[str, Any]]:
        """解码 refresh_token 并查 DB。

        抛出：
        - AUTH_REFRESH_TOKEN_INVALID：解码失败 / 已吊销 / 不存在 / 已过期
        """
        try:
            payload = decode_token(token, expected_type="refresh")
        except JWTError as exc:
            raise UnauthorizedException(
                "refresh_token 无效或已过期",
                code=AuthErrorCode.REFRESH_TOKEN_INVALID,
            ) from exc

        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedException(
                "refresh_token 缺少 jti",
                code=AuthErrorCode.REFRESH_TOKEN_INVALID,
            )

        stmt = select(RefreshToken).where(
            RefreshToken.jti == jti,
            RefreshToken.deleted_at.is_(None),
        )
        record = (await self.db.execute(stmt)).scalar_one_or_none()
        if record is None:
            raise UnauthorizedException(
                "refresh_token 不存在",
                code=AuthErrorCode.REFRESH_TOKEN_INVALID,
            )
        if record.revoked_at is not None:
            # 重复使用 → 全设备吊销（token 轮换防重放）
            await self._revoke_all_refresh_tokens(record.user_uuid)
            raise UnauthorizedException(
                "refresh_token 已被吊销",
                code=AuthErrorCode.REFRESH_TOKEN_INVALID,
            )
        if record.expires_at <= datetime.utcnow():
            raise UnauthorizedException(
                "refresh_token 已过期",
                code=AuthErrorCode.REFRESH_TOKEN_INVALID,
            )
        if record.token_hash != sha256_hex(token):
            raise UnauthorizedException(
                "refresh_token 哈希不匹配",
                code=AuthErrorCode.REFRESH_TOKEN_INVALID,
            )
        return record, payload

    async def _revoke_all_refresh_tokens(self, user_uuid: str) -> int:
        """撤销某用户所有未吊销的 refresh_token。"""
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_uuid == user_uuid,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.deleted_at.is_(None),
            )
            .values(revoked_at=datetime.utcnow())
        )
        result = await self.db.execute(stmt)
        return result.rowcount or 0

    # =======================================================================
    # 登录分发
    # =======================================================================

    async def login(
        self,
        provider: Literal["password", "phone_sms", "email_code"],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """登录分发。"""
        if provider == "password":
            user = await self._login_password(payload)
        elif provider == "phone_sms":
            user = await self._login_phone_sms(payload)
        elif provider == "email_code":
            user = await self._login_email_code(payload)
        else:
            raise ValidationException(
                f"不支持的登录方式: {provider}",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        try:
            await self._ensure_active(user)
        except UnauthorizedException as e:
            await self._record_login_log(
                user_uuid=user.uuid,
                provider=provider,
                login_status=LoginStatus.failed,
                fail_reason=e.message,
            )
            raise
        tokens = await self._issue_token_pair(user)
        await self._record_login_log(
            user_uuid=user.uuid,
            provider=provider,
            login_status=LoginStatus.success,
        )
        return {
            **tokens,
            "user": self._user_to_out(user),
            "is_new_user": False,
        }

    async def _login_password(self, payload: dict[str, Any]) -> User:
        identifier = (payload.get("identifier") or "").strip()
        password = payload.get("password") or ""
        if not identifier or not password:
            raise ValidationException(
                "identifier 与 password 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )
        # identifier 可能是邮箱或手机号；password provider 的 provider_uid 存邮箱
        # 简化：identifier 当作 email 处理（Phase 3 mock）
        identity = await self._find_identity(provider=AuthProvider.password, provider_uid=identifier)
        if identity is None:
            await self._record_login_log(
                user_uuid=None,
                provider="password",
                login_status=LoginStatus.failed,
                fail_reason="账号或密码错误",
            )
            raise UnauthorizedException(
                "账号或密码错误",
                code=AuthErrorCode.INVALID_CREDENTIALS,
            )
        user = await self._get_user(identity.user_uuid)
        if user is None or not verify_password(password, identity.credentials or ""):
            await self._record_login_log(
                user_uuid=identity.user_uuid,
                provider="password",
                login_status=LoginStatus.failed,
                fail_reason="账号或密码错误",
            )
            raise UnauthorizedException(
                "账号或密码错误",
                code=AuthErrorCode.INVALID_CREDENTIALS,
            )
        return user

    async def _login_phone_sms(self, payload: dict[str, Any]) -> User:
        phone = (payload.get("phone") or "").strip()
        code = (payload.get("code") or "").strip()
        if not phone or not code:
            raise ValidationException(
                "phone 与 code 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )
        await self._verify_code("sms", phone, code)
        identity = await self._find_identity(provider=AuthProvider.phone_sms, provider_uid=phone)
        if identity is None:
            await self._record_login_log(
                user_uuid=None,
                provider="phone_sms",
                login_status=LoginStatus.failed,
                fail_reason="该手机号未注册",
            )
            raise UnauthorizedException(
                "该手机号未注册",
                code=AuthErrorCode.INVALID_CREDENTIALS,
            )
        user = await self._get_user(identity.user_uuid)
        if user is None:
            await self._record_login_log(
                user_uuid=identity.user_uuid,
                provider="phone_sms",
                login_status=LoginStatus.failed,
                fail_reason="账号不存在",
            )
            raise UnauthorizedException(
                "账号不存在",
                code=AuthErrorCode.USER_NOT_FOUND,
            )
        return user

    async def _login_email_code(self, payload: dict[str, Any]) -> User:
        email = (payload.get("email") or "").strip()
        code = (payload.get("code") or "").strip()
        if not email or not code:
            raise ValidationException(
                "email 与 code 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )
        await self._verify_code("email", email.lower(), code)
        identity = await self._find_identity(provider=AuthProvider.email_code, provider_uid=email.lower())
        if identity is None:
            await self._record_login_log(
                user_uuid=None,
                provider="email_code",
                login_status=LoginStatus.failed,
                fail_reason="该邮箱未注册",
            )
            raise UnauthorizedException(
                "该邮箱未注册",
                code=AuthErrorCode.INVALID_CREDENTIALS,
            )
        user = await self._get_user(identity.user_uuid)
        if user is None:
            await self._record_login_log(
                user_uuid=identity.user_uuid,
                provider="email_code",
                login_status=LoginStatus.failed,
                fail_reason="账号不存在",
            )
            raise UnauthorizedException(
                "账号不存在",
                code=AuthErrorCode.USER_NOT_FOUND,
            )
        return user

    # =======================================================================
    # 注册
    # =======================================================================

    async def register(
        self,
        nickname: str,
        provider: Literal["password", "phone_sms", "email_code"],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """注册 + 自动登录。"""
        nickname = (nickname or "").strip()
        if len(nickname) < 2 or len(nickname) > 20:
            raise ValidationException(
                "昵称长度需在 2-20 字符之间",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        if provider == "password":
            identifier = (payload.get("identifier") or "").strip().lower()
            password = payload.get("password") or ""
            if not identifier or not password:
                raise ValidationException(
                    "identifier 与 password 必填",
                    code=AuthErrorCode.VALIDATION_ERROR,
                )
            if len(password) < 8:
                raise ValidationException(
                    "密码至少 8 位",
                    code=AuthErrorCode.VALIDATION_ERROR,
                )
            existing = await self._find_identity(
                provider=AuthProvider.password, provider_uid=identifier
            )
            if existing is not None:
                raise ConflictException(
                    "该邮箱已注册",
                    code=AuthErrorCode.USER_ALREADY_EXISTS,
                )
            user = await self._create_user(nickname)
            self.db.add(
                AuthIdentity(
                    user_uuid=user.uuid,
                    provider=AuthProvider.password,
                    provider_uid=identifier,
                    credentials=hash_password(password),
                )
            )
        elif provider == "phone_sms":
            phone = (payload.get("phone") or "").strip()
            code = (payload.get("code") or "").strip()
            if not phone or not code:
                raise ValidationException(
                    "phone 与 code 必填",
                    code=AuthErrorCode.VALIDATION_ERROR,
                )
            await self._verify_code("sms", phone, code)
            existing = await self._find_identity(
                provider=AuthProvider.phone_sms, provider_uid=phone
            )
            if existing is not None:
                raise ConflictException(
                    "该手机号已注册",
                    code=AuthErrorCode.USER_ALREADY_EXISTS,
                )
            user = await self._create_user(nickname)
            self.db.add(
                AuthIdentity(
                    user_uuid=user.uuid,
                    provider=AuthProvider.phone_sms,
                    provider_uid=phone,
                )
            )
        elif provider == "email_code":
            email = (payload.get("email") or "").strip().lower()
            code = (payload.get("code") or "").strip()
            if not email or not code:
                raise ValidationException(
                    "email 与 code 必填",
                    code=AuthErrorCode.VALIDATION_ERROR,
                )
            await self._verify_code("email", email, code)
            existing = await self._find_identity(
                provider=AuthProvider.email_code, provider_uid=email
            )
            if existing is not None:
                raise ConflictException(
                    "该邮箱已注册",
                    code=AuthErrorCode.USER_ALREADY_EXISTS,
                )
            user = await self._create_user(nickname)
            self.db.add(
                AuthIdentity(
                    user_uuid=user.uuid,
                    provider=AuthProvider.email_code,
                    provider_uid=email,
                )
            )
        else:
            raise ValidationException(
                f"不支持的注册方式: {provider}",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        await self.db.flush()
        tokens = await self._issue_token_pair(user)
        await self._record_login_log(
            user_uuid=user.uuid,
            provider=provider,
            login_status=LoginStatus.success,
        )
        return {
            **tokens,
            "user": self._user_to_out(user),
            "is_new_user": True,
        }

    # =======================================================================
    # Token 刷新 / 登出
    # =======================================================================

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        record, _ = await self._resolve_refresh_token(refresh_token)
        user = await self._get_user(record.user_uuid)
        if user is None:
            raise UnauthorizedException(
                "用户不存在",
                code=AuthErrorCode.USER_NOT_FOUND,
            )
        await self._ensure_active(user)

        # 旋转：撤销旧的，签发新的
        record.revoked_at = datetime.utcnow()
        await self.db.flush()
        tokens = await self._issue_token_pair(user)
        return tokens

    async def logout(self, refresh_token: str) -> dict[str, Any]:
        """幂等登出：撤销给定 refresh_token；找不到 / 已撤销都返回 200。"""
        try:
            record, _ = await self._resolve_refresh_token(refresh_token)
            record.revoked_at = datetime.utcnow()
            await self.db.flush()
            return {"revokedCount": 1}
        except UnauthorizedException:
            return {"revokedCount": 0}

    async def logout_all(self, user_uuid: str) -> dict[str, Any]:
        count = await self._revoke_all_refresh_tokens(user_uuid)
        return {"revokedCount": count}

    # =======================================================================
    # WeChat 小程序登录（mock 模式）
    # =======================================================================

    async def wechat_login(
        self,
        code: str,
        *,
        encrypted_data: str | None = None,
        iv: str | None = None,
        invite_code: str | None = None,
    ) -> dict[str, Any]:
        """微信小程序登录。

        Phase 3 mock 模式（`WX_LOGIN_MOCK=true`）：
        - 不实际调 code2session
        - 直接用 code 当作 openid 派生（hash 后取前 28 字符）
        - 已注册 → 登录；未注册 → 自动创建 user + identity
        """
        if not code:
            raise ValidationException(
                "code 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        openid = self._mock_openid_from_code(code)

        identity = await self._find_identity(
            provider=AuthProvider.wechat, provider_uid=openid
        )
        is_new_user = False
        if identity is None:
            # 自动注册：昵称暂时用 'wx_' + openid[:6]
            nickname = f"wx_{openid[:6]}"
            user = await self._create_user(nickname)
            self.db.add(
                AuthIdentity(
                    user_uuid=user.uuid,
                    provider=AuthProvider.wechat,
                    provider_uid=openid,
                )
            )
            await self.db.flush()
            is_new_user = True
        else:
            user = await self._get_user(identity.user_uuid)
            if user is None:
                await self._record_login_log(
                    user_uuid=identity.user_uuid,
                    provider="wechat",
                    login_status=LoginStatus.failed,
                    fail_reason="账号不存在",
                )
                raise UnauthorizedException(
                    "账号不存在",
                    code=AuthErrorCode.USER_NOT_FOUND,
                )
            await self._ensure_active(user)

        tokens = await self._issue_token_pair(user)
        await self._record_login_log(
            user_uuid=user.uuid,
            provider="wechat",
            login_status=LoginStatus.success,
        )
        return {
            **tokens,
            "user": self._user_to_out(user),
            "is_new_user": is_new_user,
        }

    @staticmethod
    def _mock_openid_from_code(code: str) -> str:
        """Mock 模式派生 openid：code 任意，但派生结果稳定（同一 code → 同 openid）。"""
        digest = hashlib.sha256(f"wx-mock::{code}".encode()).hexdigest()
        # 微信 openid 长度 28 字符以下；取前 28 位
        return digest[:28]

    # =======================================================================
    # ws-ticket
    # =======================================================================

    async def issue_ws_ticket(self, user_uuid: str) -> dict[str, Any]:
        ticket, expires_at = await self._new_ws_ticket()
        await store_ws_ticket(ticket, user_uuid)
        return {
            "ticket": ticket,
            "expires_in": int((expires_at - datetime.utcnow()).total_seconds()),
            "ws_url_template": "/ws/notifications?token={ticket}",
        }

    @staticmethod
    async def _new_ws_ticket() -> tuple[str, datetime]:
        """生成一次性 ticket（同步生成字符串，TTL 来自配置）。"""
        ticket = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(
            seconds=settings.WS_TICKET_EXPIRE_SECONDS
        )
        return ticket, expires_at

    # =======================================================================
    # 验证码（图形 / 短信 / 邮箱）— mock 模式存 Redis
    # =======================================================================

    async def generate_captcha(self) -> dict[str, Any]:
        """生成图形验证码。答案存 Redis（5 分钟），返回 captcha_id + 图片。"""
        from src.utils.captcha import captcha_data_uri

        answer, svg_b64 = generate_captcha()
        captcha_id = secrets.token_urlsafe(16)
        redis = get_redis()
        # 存 hash 而不是明文，避免 Redis 被 dump 后直接拿到答案
        await redis.set(
            build_key("captcha", captcha_id),
            sha256_hex(answer.upper()),
            ex=_CAPTCHA_TTL,
        )
        return {
            "captcha_id": captcha_id,
            "image": captcha_data_uri(svg_b64),
        }

    async def verify_captcha(self, captcha_id: str, solution: str) -> bool:
        if not captcha_id or not solution:
            return False
        redis = get_redis()
        key = build_key("captcha", captcha_id)
        stored = await getdel(redis, key)  # 一次性消费
        if stored is None:
            return False
        return stored == sha256_hex(solution.strip().upper())

    async def send_sms_code(
        self,
        phone: str,
        purpose: Literal["login", "register", "bind"],
        *,
        captcha_id: str | None = None,
        captcha_solution: str | None = None,
    ) -> dict[str, Any]:
        """发送短信验证码（mock：答案打印到日志，验证码写 Redis）。"""
        if not phone:
            raise ValidationException(
                "phone 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        # 图形验证码门禁（仅用于敏感场景，本接口骨架阶段不强制）
        if captcha_id and captcha_solution:
            if not await self.verify_captcha(captcha_id, captcha_solution):
                raise BusinessException(
                    "图形验证码错误或已过期",
                    code=AuthErrorCode.CAPTCHA_INVALID,
                    http_status=400,
                )

        # 限流：同号 60s 内只发一次
        redis = get_redis()
        rate_key = build_key("rate:sms", phone)
        if await redis.exists(rate_key):
            raise BusinessException(
                "请求过于频繁，请稍后再试",
                code="RATE_LIMITED",
                http_status=429,
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        await redis.set(build_key("sms:code", phone), code, ex=_SMS_CODE_TTL)
        await redis.set(rate_key, "1", ex=_SMS_RATE_LIMIT_TTL)
        # mock：打印到日志，方便本地联调
        logger.info("[SMS-MOCK] phone=%s purpose=%s code=%s", phone, purpose, code)
        return {
            "sent": True,
            "purpose": purpose,
            # 开发模式返回 code，便于自动化测试；生产应去掉
            "debug_code": code if settings.APP_ENV in {"dev", "test"} else None,
        }

    async def send_email_code(
        self,
        email: str,
        purpose: Literal["login", "register", "bind"],
    ) -> dict[str, Any]:
        """发送邮箱验证码（mock：日志 + Redis）。"""
        email = (email or "").strip().lower()
        if not email:
            raise ValidationException(
                "email 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        redis = get_redis()
        rate_key = build_key("rate:email", email)
        if await redis.exists(rate_key):
            raise BusinessException(
                "请求过于频繁，请稍后再试",
                code="RATE_LIMITED",
                http_status=429,
            )

        code = f"{secrets.randbelow(1_000_000):06d}"
        await redis.set(build_key("email:code", email), code, ex=_EMAIL_CODE_TTL)
        await redis.set(rate_key, "1", ex=_SMS_RATE_LIMIT_TTL)
        logger.info("[EMAIL-MOCK] email=%s purpose=%s code=%s", email, purpose, code)
        return {
            "sent": True,
            "purpose": purpose,
            "debug_code": code if settings.APP_ENV in {"dev", "test"} else None,
        }

    async def _verify_code(self, kind: Literal["sms", "email"], identifier: str, code: str) -> None:
        """校验 sms / email 验证码。成功后立即消费。"""
        redis = get_redis()
        key = build_key(f"{kind}:code", identifier)
        stored = await getdel(redis, key)
        if stored is None:
            raise BusinessException(
                "验证码已过期",
                code=AuthErrorCode.CODE_EXPIRED,
                http_status=400,
            )
        if stored != code:
            raise BusinessException(
                "验证码错误",
                code=AuthErrorCode.CODE_INVALID,
                http_status=400,
            )

    # =======================================================================
    # 登录方式 / 密码重置
    # =======================================================================

    async def list_login_methods(self) -> dict[str, Any]:
        """返回当前可用的登录方式列表（骨架阶段全部启用）。"""
        return {
            "methods": [
                {"provider": "password", "identifier_type": "email", "enabled": True},
                {"provider": "phone_sms", "identifier_type": "phone", "enabled": True},
                {"provider": "email_code", "identifier_type": "email", "enabled": True},
                {"provider": "wechat", "identifier_type": "openid", "enabled": True},
            ],
            "captcha_enabled": True,
        }

    async def request_password_reset(self, email: str) -> dict[str, Any]:
        """请求密码重置（mock：无论邮箱是否存在都返回 200 防止账号枚举）。

        真实流程：发邮件 → 用户点链接 → reset_token 入库；
        Mock 流程：reset_token 直接返回给调用方（仅 dev/test）。
        """
        email = (email or "").strip().lower()
        identity = None
        if email:
            identity = await self._find_identity(
                provider=AuthProvider.password, provider_uid=email
            )
        if identity is not None:
            token = secrets.token_urlsafe(32)
            redis = get_redis()
            await redis.set(
                build_key("password:reset", token),
                identity.user_uuid,
                ex=_RESET_TOKEN_TTL,
            )
            logger.info(
                "[RESET-MOCK] email=%s token=%s", email, token
            )
            return {
                "sent": True,
                "debug_token": token if settings.APP_ENV in {"dev", "test"} else None,
            }
        # 即便邮箱不存在也返回 200
        return {"sent": True, "debug_token": None}

    async def do_password_reset(self, reset_token: str, new_password: str) -> dict[str, Any]:
        """使用 reset_token 重置密码。成功后吊销所有 refresh_token。"""
        if not reset_token or not new_password:
            raise ValidationException(
                "reset_token 与 new_password 必填",
                code=AuthErrorCode.VALIDATION_ERROR,
            )
        if len(new_password) < 8:
            raise ValidationException(
                "密码至少 8 位",
                code=AuthErrorCode.VALIDATION_ERROR,
            )

        redis = get_redis()
        key = build_key("password:reset", reset_token)
        user_uuid = await getdel(redis, key)
        if isinstance(user_uuid, bytes):
            user_uuid = user_uuid.decode("utf-8")
        if not user_uuid:
            raise BusinessException(
                "reset_token 无效或已过期",
                code=AuthErrorCode.RESET_TOKEN_INVALID,
                http_status=400,
            )

        identity = await self._find_identity(
            provider=AuthProvider.password, user_uuid=user_uuid
        )
        if identity is None:
            raise NotFoundException(
                "账号不存在", code=AuthErrorCode.USER_NOT_FOUND
            )
        identity.credentials = hash_password(new_password)
        await self.db.flush()

        # 吊销全部 refresh_token（防被盗号）
        await self._revoke_all_refresh_tokens(user_uuid)
        return {"message": "密码重置成功"}

    # =======================================================================
    # 内部辅助
    # =======================================================================

    async def _find_identity(
        self,
        *,
        provider: AuthProvider,
        provider_uid: str | None = None,
        user_uuid: str | None = None,
    ) -> AuthIdentity | None:
        stmt = select(AuthIdentity).where(
            AuthIdentity.provider == provider,
            AuthIdentity.deleted_at.is_(None),
        )
        if provider_uid is not None:
            stmt = stmt.where(AuthIdentity.provider_uid == provider_uid)
        if user_uuid is not None:
            stmt = stmt.where(AuthIdentity.user_uuid == user_uuid)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def _get_user(self, user_uuid: str) -> User | None:
        stmt = select(User).where(
            User.uuid == user_uuid,
            User.deleted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _create_user(self, nickname: str) -> User:
        user = User(
            nickname=nickname,
            role=UserRole.user,
            status=UserStatus.active,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def _ensure_active(self, user: User) -> None:
        if user.status == UserStatus.banned:
            raise UnauthorizedException(
                "账号已被封禁", code="AUTH_USER_BANNED"
            )
        if user.status == UserStatus.disabled:
            raise UnauthorizedException(
                "账号已被禁用", code="AUTH_USER_DISABLED"
            )
        if user.status == UserStatus.deleted:
            raise UnauthorizedException(
                "账号不存在", code=AuthErrorCode.USER_NOT_FOUND
            )

    @staticmethod
    def _user_to_out(user: User) -> dict[str, Any]:
        return {
            "uuid": user.uuid,
            "nickname": user.nickname,
            "avatarUrl": user.avatar_url,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "status": user.status.value if hasattr(user.status, "value") else str(user.status),
            "locale": user.locale,
        }

    async def _record_login_log(
        self,
        *,
        user_uuid: str | None,
        provider: str,
        login_status: LoginStatus,
        fail_reason: str | None = None,
    ) -> None:
        """Record a login attempt (success or failure) with IP / UA captured from the request.

        Uses a synchronous connection to ensure the log is persisted even when
        the parent async transaction is rolled back due to an auth error."""
        ip = getattr(self, "_request_ip", None) or None
        ua = getattr(self, "_request_ua", None) or None

        from sqlalchemy import create_engine
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        sync_url = settings.DATABASE_URL.replace("mysql+aiomysql", "mysql+pymysql")
        engine = create_engine(sync_url, pool_pre_ping=True)

        with engine.begin() as conn:
            stmt = mysql_insert(LoginLog).values(
                uuid=str(_uuid_lib.uuid4()),
                user_uuid=user_uuid,
                provider=provider,
                ip_address=ip,
                user_agent=ua,
                login_status=login_status,
                fail_reason=fail_reason,
                created_at=datetime.utcnow(),
            )
            conn.execute(stmt)

        engine.dispose()


__all__ = ["AuthService", "AuthErrorCode"]