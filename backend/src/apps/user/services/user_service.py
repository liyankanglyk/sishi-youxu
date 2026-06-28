"""User profile service — Phase 3 implementation.

Covers:
- Profile update (nickname, locale, avatar)
- Password change (with old-password verification + revoke all tokens)
- Avatar upload (local file storage in dev; CDN in prod)
- Auth-linkage (list / bind / unbind providers)
- Reminder channels (skeleton placeholder)
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

_LINK_TOKEN_TTL = 300  # 5 minutes


class UserService:
    """User profile & account management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # Profile
    # =========================================================================

    async def get_me(self, user_uuid: str) -> dict[str, Any]:
        """Return current user profile."""
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")
        return self._user_to_profile(user)

    async def update_me(self, user_uuid: str, data: dict[str, Any]) -> dict[str, Any]:
        """Update current user profile fields (nickname, locale)."""
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
    # Password
    # =========================================================================

    async def change_password(
        self, user_uuid: str, old_password: str, new_password: str
    ) -> dict[str, Any]:
        """Change password: verify old, set new, revoke all refresh tokens."""
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

        # Find password identity for this user
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

        # Revoke all refresh tokens → force re-login on all devices
        revoked = await self._revoke_all_refresh_tokens(user_uuid)
        logger.info("password changed for user=%s, revoked %d refresh tokens", user_uuid, revoked)

        return {"message": "密码修改成功"}

    # =========================================================================
    # Avatar
    # =========================================================================

    async def upload_avatar(
        self, user_uuid: str, file_content: bytes, filename: str
    ) -> dict[str, Any]:
        """Save avatar file and update user's avatar_url.

        Dev mode: save to local ``backend/avatars/`` directory.
        Production: expects CDN/S3 upload (placeholder).
        """
        user = await self._get_user(user_uuid)
        if user is None:
            raise NotFoundException("用户不存在", code="USER_NOT_FOUND")

        # Validate file type
        ext = os.path.splitext(filename)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValidationException(
                "仅支持 JPG/PNG/WebP 格式",
                code="VALIDATION_ERROR",
                detail={"file": "头像图片仅支持 JPG/PNG/WebP 格式"},
            )

        # 2 MB max
        max_size = 2 * 1024 * 1024
        if len(file_content) > max_size:
            raise ValidationException(
                "图片大小不能超过 2MB",
                code="VALIDATION_ERROR",
                detail={"file": "头像图片最大 2MB"},
            )

        # Dev: save to local directory
        avatars_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "avatars",
        )
        os.makedirs(avatars_dir, exist_ok=True)

        save_name = f"{user_uuid}{ext}"
        save_path = os.path.join(avatars_dir, save_name)
        with open(save_path, "wb") as f:
            f.write(file_content)

        # Build avatar URL
        avatar_url = f"/avatars/{save_name}"
        user.avatar_url = avatar_url
        await self.db.flush()
        await self.db.refresh(user)

        return {
            "avatarUrl": avatar_url,
            "updatedAt": user.updated_at.isoformat() if user.updated_at else datetime.utcnow().isoformat(),
        }

    # =========================================================================
    # Auth Linkage
    # =========================================================================

    async def create_link_token(self, user_uuid: str) -> dict[str, Any]:
        """Generate a temporary link_token for binding a new auth provider."""
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
        """List currently bound auth providers with masked identifiers."""
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
        """Bind a new auth provider (phone_sms / email_code) to the current account."""
        if provider not in {"phone_sms", "email_code"}:
            raise ValidationException(
                f"不支持的绑定方式: {provider}",
                code="VALIDATION_ERROR",
            )

        # Verify link_token
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

        # Verify code
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

        # Check if already bound
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

        # Create identity
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
        """Unbind an auth provider from the current account."""
        if provider not in {"phone_sms", "email_code", "wechat"}:
            raise ValidationException(
                f"不支持解绑该登录方式: {provider}",
                code="VALIDATION_ERROR",
            )

        auth_provider = AuthProvider(provider)

        # Count how many identities this user has; prevent removing the last one
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
    # Internal helpers
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
        """Verify sms / email code from Redis (one-time consumption)."""
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
        """Mask identifier for safe display.

        Email: u***@example.com (keep first char + domain)
        Phone: +86 138****1234 (keep prefix + last 4)
        """
        if provider in ("password", "email_code"):
            if "@" in identifier:
                local, domain = identifier.split("@", 1)
                local_masked = local[0] + "***" if len(local) > 0 else "***"
                return f"{local_masked}@{domain}"
            return identifier[0] + "***" if len(identifier) > 0 else "***"
        if provider == "phone_sms":
            # Keep country code + first 3 digits + **** + last 4
            if len(identifier) >= 11:
                return f"{identifier[:7]}****{identifier[-4:]}"
            return identifier[:3] + "****" + identifier[-4:] if len(identifier) > 7 else identifier[:1] + "****"
        if provider == "wechat":
            return "微信用户"
        return identifier


__all__ = ["UserService"]
