"""用户资料 service —— Phase 3 实现。

包含：
- 资料更新（昵称、语言偏好、头像）
- 修改密码（校验旧密码 + 撤销所有 token）
- 上传头像（开发模式存本地，生产模式走 CDN）
- 第三方登录绑定（列出 / 绑定 / 解绑）
- 提醒渠道（骨架占位）
"""

from __future__ import annotations

import os
import secrets
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Any, Literal

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
from src.core.security import hash_password, sha256_hex, verify_password
from src.models.auth import AuthIdentity, AuthProvider, RefreshToken
from src.models.user import User, UserStatus

logger = get_logger(__name__)

_LINK_TOKEN_TTL = 300  # 5 分钟


class UserService:
    """用户资料与账户管理。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # 资料
    # =========================================================================

    async def get_me(self, user_uuid: str) -> dict[str, Any]:
        """返回当前用户的资料。"""
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")
        return self._user_to_profile(user)

    async def update_me(self, user_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """更新当前用户的资料字段（昵称、语言偏好）。"""
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        changed = False
        if "nickname" in data:
            nickname = (data["nickname"] or "").strip()
            if len(nickname) < 2 or len(nickname) > 20:
                raise ValidationException(
                    "昵称长度需在 2-20 字符之间",
                    code="VALIDATION_ERROR",
                    detail={"nickname": "昵称长度必须在 2-20 字符之间"},
                )
            user.nickname = nickname
            changed = True

        if "locale" in data:
            locale = (data["locale"] or "").strip()
            if locale and len(locale) <= 10:
                user.locale = locale
                changed = True

        if "avatar_url" in data:
            user.avatar_url = data["avatar_url"]
            changed = True

        if changed:
            await self.db.flush()
            await self.db.refresh(user)

        return self._user_to_profile(user)

    # =========================================================================
    # 密码
    # =========================================================================

    async def change_password(
        self, user_uuid: str, old_password: str, new_password: str
    ) -> dict[str, Any]:
        """修改密码：校验旧密码、设置新密码、撤销所有 refresh token。"""
        if not old_password or not new_password:
            raise ValidationException(
                "oldPassword 与 newPassword 必填",
                code="VALIDATION_ERROR",
            )
        if len(new_password) < 8:
            raise ValidationException(
                "密码至少 8 位",
                code="VALIDATION_ERROR",
                detail={"newPassword": "密码最少 8 字符"},
            )

        # 查找该用户的密码登录身份
        identity = await self._find_identity(
            provider=AuthProvider.password, user_uuid=user_uuid
        )
        if identity is None:
            raise NotFoundException(
                "未设置密码登录方式",
                code="AUTH_PROVIDER_NOT_LINKED",
            )
        if not verify_password(old_password, identity.credentials or ""):
            raise ValidationException(
                "当前密码错误",
                code="AUTH_INVALID_CREDENTIALS",
                detail={"oldPassword": "当前密码不正确"},
            )

        identity.credentials = hash_password(new_password)
        await self.db.flush()

        # 撤销所有 refresh token → 强制所有设备重新登录
        revoked = await self._revoke_all_refresh_tokens(user_uuid)
        logger.info("password changed for user=%s, revoked %d refresh tokens", user_uuid, revoked)

        return {"message": "密码修改成功"}

    # =========================================================================
    # 头像
    # =========================================================================

    async def upload_avatar(
        self, user_uuid: str, file_content: bytes, filename: str
    ) -> dict[str, Any]:
        """保存头像文件并更新用户的 avatar_url。

        开发模式：保存到本地 ``backend/avatars/`` 目录。
        生产模式：预期走 CDN/S3 上传（占位）。
        """
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        # 校验文件类型
        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValidationException(
                "仅支持 JPG/PNG/WebP 格式",
                code="VALIDATION_ERROR",
                detail={"file": "头像图片仅支持 JPG/PNG/WebP 格式"},
            )

        # 最大 2MB
        max_size = 2 * 1024 * 1024
        if len(file_content) > max_size:
            raise ValidationException(
                "图片大小不能超过 2MB",
                code="VALIDATION_ERROR",
                detail={"file": "头像图片最大 2MB"},
            )

        # 开发模式：保存到本地目录
        avatars_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "avatars",
        )
        os.makedirs(avatars_dir, exist_ok=True)

        save_name = f"{user_uuid}{ext}"
        save_path = os.path.join(avatars_dir, save_name)
        with open(save_path, "wb") as f:
            f.write(file_content)

        # 构造头像 URL
        avatar_url = f"/avatars/{save_name}"
        user.avatar_url = avatar_url
        await self.db.flush()
        await self.db.refresh(user)

        return {
            "avatarUrl": avatar_url,
            "updatedAt": user.updated_at.isoformat() if user.updated_at else datetime.utcnow().isoformat(),
        }

    # =========================================================================
    # 第三方登录绑定
    # =========================================================================

    async def create_link_token(self, user_uuid: str) -> dict[str, Any]:
        """生成用于绑定新登录方式的临时 link_token。"""
        token = secrets.token_urlsafe(32)
        redis = get_redis()
        await redis.set(
            build_key("link:token", token),
            user_uuid,
            ex=_LINK_TOKEN_TTL,
        )
        return {
            "link_token": token,
            "expires_in": _LINK_TOKEN_TTL,
        }

    async def list_linkage(self, user_uuid: str) -> dict[str, Any]:
        """列出已绑定的登录方式，标识脱敏显示。"""
        stmt = select(AuthIdentity).where(
            AuthIdentity.user_uuid == user_uuid,
            AuthIdentity.deleted_at.is_(None),
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        items = []
        for r in rows:
            provider = r.provider.value if hasattr(r.provider, "value") else str(r.provider)
            identifier = r.provider_uid or ""
            masked = self._mask_identifier(provider, identifier)
            items.append({
                "provider": provider,
                "identifier": masked,
                "boundAt": r.created_at.isoformat() if r.created_at else None,
            })

        return {"items": items}

    async def bind_provider(
        self,
        user_uuid: str,
        provider: str,
        link_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """为当前账号绑定新的登录方式（phone_sms / email_code）。"""
        if provider not in {"phone_sms", "email_code"}:
            raise ValidationException(
                f"不支持的绑定方式: {provider}",
                code="VALIDATION_ERROR",
            )

        # 校验 link_token
        redis = get_redis()
        key = build_key("link:token", link_token)
        stored_user = await getdel(redis, key)
        if isinstance(stored_user, bytes):
            stored_user = stored_user.decode("utf-8")
        if stored_user != user_uuid:
            raise UnauthorizedException(
                "绑定令牌无效或已过期",
                code="AUTH_LINK_TOKEN_INVALID",
            )

        # 校验验证码
        auth_provider = AuthProvider(provider)
        identifier: str
        code: str
        if provider == "phone_sms":
            identifier = (payload.get("phone") or payload.get("identifier") or "").strip()
            code = (payload.get("code") or "").strip()
        else:
            identifier = (payload.get("email") or payload.get("identifier") or "").strip().lower()
            code = (payload.get("code") or "").strip()

        if not identifier or not code:
            raise ValidationException(
                "identifier 与 code 必填",
                code="VALIDATION_ERROR",
            )

        await self._verify_code(
            "sms" if provider == "phone_sms" else "email",
            identifier,
            code,
        )

        # 检查是否已被绑定
        existing = await self._find_identity(provider=auth_provider, provider_uid=identifier)
        if existing is not None:
            if existing.user_uuid == user_uuid:
                raise ConflictException(
                    "该登录方式已绑定",
                    code="AUTH_PROVIDER_ALREADY_LINKED",
                )
            raise ConflictException(
                "该标识已被其他账号绑定",
                code="USER_ALREADY_EXISTS",
            )

        # 创建身份记录
        self.db.add(
            AuthIdentity(
                user_uuid=user_uuid,
                provider=auth_provider,
                provider_uid=identifier,
            )
        )
        await self.db.flush()

        return {
            "provider": provider,
            "identifier": self._mask_identifier(provider, identifier),
            "boundAt": datetime.utcnow().isoformat(),
        }

    async def unbind_provider(self, user_uuid: str, provider: str) -> dict[str, Any]:
        """解绑当前账号的某个登录方式。"""
        if provider not in {"phone_sms", "email_code", "wechat"}:
            raise ValidationException(
                f"不支持解绑该登录方式: {provider}",
                code="VALIDATION_ERROR",
            )

        auth_provider = AuthProvider(provider)

        # 统计该用户拥有的登录身份数量，避免移除最后一个
        count_stmt = select(AuthIdentity).where(
            AuthIdentity.user_uuid == user_uuid,
            AuthIdentity.deleted_at.is_(None),
        )
        all_identities = (await self.db.execute(count_stmt)).scalars().all()
        if len(all_identities) <= 1:
            raise ConflictException(
                "至少需要保留一种登录方式",
                code="VALIDATION_ERROR",
                detail={"provider": "不能解绑唯一的登录方式"},
            )

        identity = await self._find_identity(provider=auth_provider, user_uuid=user_uuid)
        if identity is None:
            raise NotFoundException(
                "该登录方式未绑定",
                code="AUTH_PROVIDER_NOT_LINKED",
            )

        identity.deleted_at = datetime.utcnow()
        await self.db.flush()

        return {"unbound": provider}

    # =========================================================================
    # 内部辅助
    # =========================================================================

    async def _get_user(self, user_uuid: str) -> User | None:
        stmt = select(User).where(
            User.uuid == user_uuid,
            User.deleted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

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

    async def _revoke_all_refresh_tokens(self, user_uuid: str) -> int:
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

    async def _verify_code(
        self, kind: Literal["sms", "email"], identifier: str, code: str
    ) -> None:
        """从 Redis 中校验 sms / email 验证码（一次性消费）。"""
        redis = get_redis()
        key = build_key(f"{kind}:code", identifier)
        stored = await getdel(redis, key)
        if stored is None:
            raise BusinessException(
                "验证码已过期",
                code="AUTH_CODE_EXPIRED",
                http_status=400,
            )
        if stored != code:
            raise BusinessException(
                "验证码错误",
                code="AUTH_CODE_INVALID",
                http_status=400,
            )

    @staticmethod
    def _user_to_profile(user: User) -> dict[str, Any]:
        return {
            "uuid": user.uuid,
            "nickname": user.nickname,
            "avatarUrl": user.avatar_url,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
            "status": user.status.value if hasattr(user.status, "value") else str(user.status),
            "locale": user.locale,
            "createdAt": user.created_at.isoformat() if user.created_at else None,
            "updatedAt": user.updated_at.isoformat() if user.updated_at else None,
        }

    @staticmethod
    def _mask_identifier(provider: str, identifier: str) -> str:
        """对标识进行脱敏以便安全展示。

        邮箱：u***@example.com（保留首字母 + 域名）
        手机号：+86 138****1234（保留前缀 + 末四位）
        """
        if provider in ("password", "email_code"):
            if "@" in identifier:
                local, domain = identifier.split("@", 1)
                local_masked = local[0] + "***" if len(local) > 0 else "***"
                return f"{local_masked}@{domain}"
            return identifier[0] + "***" if len(identifier) > 0 else "***"
        if provider == "phone_sms":
            # 保留国家码 + 前 3 位 + **** + 末四位
            if len(identifier) >= 11:
                return f"{identifier[:7]}****{identifier[-4:]}"
            return identifier[:3] + "****" + identifier[-4:] if len(identifier) > 7 else identifier[:1] + "****"
        if provider == "wechat":
            return "微信用户"
        return identifier


__all__ = ["UserService"]
