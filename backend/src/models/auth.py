"""认证相关模型骨架（身份、刷新令牌）。

设计要点：

- `AuthProvider` 枚举必须包含 `wechat`，因为微信小程序登录走
  `sishiyouxu_auth_identity` 的同一张表，仅 `provider` 字段不同
- `provider_uid` 对微信存 openid（28 字符以内）；对 phone_sms 存手机号；
  对 email_code 存邮箱；对 password 存 username。VARCHAR(255) 足够
- `credentials` 对 password 存 bcrypt 哈希；其他场景存 NULL 或加密的 token
- 联合唯一约束 `(provider, provider_uid)` —— 同一 provider 下 provider_uid
  不能重复
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import CHAR, DateTime, Enum, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class AuthProvider(str, enum.Enum):
    """登录方式枚举。

    新增 `wechat` 后，Provider 集合为：
      - password    : 账号 + 密码（Web/Capacitor 通用）
      - phone_sms   : 手机号 + 短信验证码（mock 阶段）
      - email_code  : 邮箱 + 验证码（mock 阶段）
      - wechat      : 微信小程序 code2session
    """

    password = "password"
    phone_sms = "phone_sms"
    email_code = "email_code"
    wechat = "wechat"


class AuthIdentity(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_auth_identity"
    __table_args__ = (
        UniqueConstraint("provider", "provider_uid", name="uk_provider_uid"),
    )

    user_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    provider: Mapped[AuthProvider] = mapped_column(
        Enum(AuthProvider, native_enum=False, length=20), nullable=False
    )
    provider_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    credentials: Mapped[str | None] = mapped_column(Text, nullable=True)


class RefreshToken(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sishiyouxu_refresh_token"

    user_uuid: Mapped[str] = mapped_column(CHAR(36), nullable=False, index=True)
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
