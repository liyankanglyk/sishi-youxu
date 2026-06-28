"""认证相关 DTO（骨架）。

设计要点（兼容微信小程序）：
- `LoginRequest.provider` 字面量新增 `wechat`
- `WechatLoginRequest`：小程序 `wx.login()` 拿到的 code + 可选加密数据
- `WsTicketRequest` / `WsTicketResponse`：ws 一次性 ticket
  （小程序 `wx.connectSocket` 走 `?token=<ticket>`）
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 枚举 / 字面量
# ---------------------------------------------------------------------------
ProviderLiteral = Literal["password", "phone_sms", "email_code", "wechat"]
SmsPurposeLiteral = Literal["login", "register", "bind"]
EmailPurposeLiteral = Literal["login", "register", "bind"]


# ---------------------------------------------------------------------------
# 请求 DTO
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    """账号登录请求。

    provider 可选：
    - `password`：账号密码登录（payload.identifier + payload.password）
    - `phone_sms`：手机号+短信验证码（payload.phone + payload.code）
    - `email_code`：邮箱+邮箱验证码（payload.email + payload.code）
    """

    provider: ProviderLiteral = Field(..., description="登录方式")
    payload: dict = Field(default_factory=dict, description="认证凭据，结构因 provider 而异")


class WechatLoginRequest(BaseModel):
    """微信小程序登录请求。

    - code: 必填，`wx.login()` 拿到的临时凭证
    - encrypted_data / iv: 可选，用于解密手机号/用户信息（非必需）
    - invite_code: 可选，邀请码（运营位）
    """

    code: str = Field(..., min_length=1, max_length=128, description="wx.login() 临时凭证")
    encrypted_data: Optional[str] = Field(default=None, max_length=512, description="加密数据（解密手机号用）")
    iv: Optional[str] = Field(default=None, max_length=64, description="解密向量")
    invite_code: Optional[str] = Field(default=None, max_length=32, description="邀请码")


class RefreshRequest(BaseModel):
    """刷新 Token 请求。"""

    refreshToken: str = Field(..., description="刷新令牌", alias="refresh_token")

    model_config = {"populate_by_name": True}


class LogoutRequest(BaseModel):
    """登出请求。"""

    refreshToken: str = Field(..., description="要撤销的刷新令牌", alias="refresh_token")

    model_config = {"populate_by_name": True}


class CaptchaVerifyRequest(BaseModel):
    """校验图形验证码请求。"""

    captchaId: str = Field(..., description="图形验证码 ID", alias="captcha_id")
    captchaSolution: str = Field(..., description="用户输入的验证码", alias="captcha_solution")

    model_config = {"populate_by_name": True}


class SmsCodeSendRequest(BaseModel):
    """发送短信验证码请求。"""

    phone: str = Field(..., description="手机号，格式 +86 开头")
    purpose: SmsPurposeLiteral = Field(default="login", description="用途：login / register / bind")
    captchaId: Optional[str] = Field(default=None, description="图形验证码 ID（连续失败后需要）")
    captchaSolution: Optional[str] = Field(default=None, description="图形验证码答案")


class SmsCodeLoginRequest(BaseModel):
    """短信验证码登录请求。"""

    phone: str = Field(..., description="手机号")
    code: str = Field(..., min_length=6, max_length=6, description="6 位短信验证码")


class EmailCodeSendRequest(BaseModel):
    """发送邮箱验证码请求。"""

    email: str = Field(..., description="邮箱地址")
    purpose: EmailPurposeLiteral = Field(default="login", description="用途：login / register / bind")


class EmailCodeLoginRequest(BaseModel):
    """邮箱验证码登录请求。"""

    email: str = Field(..., description="邮箱地址")
    code: str = Field(..., min_length=6, max_length=6, description="6 位邮箱验证码")


class PasswordResetRequest(BaseModel):
    """密码重置请求。"""

    resetToken: str = Field(..., description="邮件中的重置令牌", alias="reset_token")
    newPassword: str = Field(..., min_length=8, max_length=128, description="新密码（最少 8 位，含大小写字母和数字）", alias="new_password")

    model_config = {"populate_by_name": True}


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    nickname: str = Field(..., min_length=2, max_length=20, description="昵称")
    provider: ProviderLiteral = Field(..., description="注册方式：password / phone_sms / email_code")
    payload: dict = Field(default_factory=dict, description="凭据对象，因 provider 而异")


# ---------------------------------------------------------------------------
# 响应 DTO
# ---------------------------------------------------------------------------
class UserOut(BaseModel):
    """用户信息（登录/注册响应中返回）。"""

    uuid: str = Field(..., description="用户唯一标识")
    nickname: str = Field(..., description="昵称")
    avatarUrl: Optional[str] = Field(default=None, description="头像 URL")
    role: str = Field(default="user", description="角色：user / admin / super_admin")
    status: str = Field(default="active", description="状态：active / disabled / banned")
    locale: str = Field(default="zh-CN", description="语言偏好")


class TokenRefreshResponse(BaseModel):
    """Token 刷新响应。"""

    access_token: str = Field(..., description="新的访问令牌")
    refresh_token: str = Field(..., description="新的刷新令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(default=1800, description="access_token 有效期（秒）")


class LoginResponse(BaseModel):
    """登录/注册成功响应。"""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="Bearer", description="令牌类型")
    expires_in: int = Field(default=1800, description="access_token 有效期（秒）")
    user: UserOut = Field(..., description="用户信息")
    is_new_user: bool = Field(default=False, description="是否新注册用户")


class LogoutResponse(BaseModel):
    """登出响应。"""

    revokedCount: int = Field(default=0, description="已撤销的 token 数量")


class LoginMethodItem(BaseModel):
    """单个登录方式。"""

    provider: str = Field(..., description="登录方式")
    identifier_type: str = Field(..., description="标识类型：email / phone")
    enabled: bool = Field(..., description="是否启用")


class LoginMethodsResponse(BaseModel):
    """可用登录方式响应。"""

    methods: list[LoginMethodItem] = Field(default_factory=list, description="登录方式列表")
    captcha_enabled: bool = Field(default=True, description="是否需要图形验证码")


class CaptchaResponse(BaseModel):
    """图形验证码响应。"""

    captcha_id: str = Field(..., description="验证码 ID（UUID）")
    image: str = Field(..., description="Base64 编码的验证码图片（data:image/svg+xml;base64,...）")


class CaptchaVerifyResponse(BaseModel):
    """图形验证码校验响应。"""

    verified: bool = Field(..., description="是否验证通过")


class WsTicketResponse(BaseModel):
    """WebSocket Ticket 响应。"""

    ticket: str = Field(..., description="一次性 ticket（用于 ws 连接）")
    expires_in: int = Field(default=30, description="有效期（秒）")
    ws_url_template: str = Field(default="/ws/notifications?token={ticket}", description="WebSocket 连接 URL 模板")


class PasswordResetResponse(BaseModel):
    """密码重置响应。"""

    message: str = Field(default="密码重置成功", description="提示信息")


# ---------------------------------------------------------------------------
# 用户资料 DTO
# ---------------------------------------------------------------------------
class UpdateProfileRequest(BaseModel):
    """更新个人资料请求。"""

    nickname: Optional[str] = Field(default=None, min_length=2, max_length=20, description="新昵称")
    locale: Optional[str] = Field(default=None, max_length=10, description="语言偏好")


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""

    oldPassword: str = Field(..., min_length=1, description="当前密码")
    newPassword: str = Field(..., min_length=8, max_length=128, description="新密码（最少 8 位，含大小写字母和数字）")


class ChangePasswordResponse(BaseModel):
    """修改密码响应。"""

    message: str = Field(default="密码修改成功", description="提示信息")


class AvatarUploadResponse(BaseModel):
    """头像上传响应。"""

    avatarUrl: str = Field(..., description="头像 URL")
    updatedAt: str = Field(..., description="更新时间（ISO 8601）")


class LinkTokenResponse(BaseModel):
    """绑定 Token 响应。"""

    linkToken: str = Field(..., description="绑定令牌", alias="link_token")
    expires_in: int = Field(default=300, description="有效期（秒）")

    model_config = {"populate_by_name": True}


class AuthLinkageItem(BaseModel):
    """已绑定登录方式条目。"""

    provider: str = Field(..., description="登录方式")
    identifier: str = Field(..., description="脱敏后的标识")
    boundAt: Optional[str] = Field(default=None, description="绑定时间（ISO 8601）")


class AuthLinkageListResponse(BaseModel):
    """已绑定登录方式列表响应。"""

    items: list[AuthLinkageItem] = Field(default_factory=list)


class BindProviderRequest(BaseModel):
    """绑定新登录方式请求。"""

    linkToken: str = Field(..., description="绑定令牌", alias="link_token")
    payload: dict = Field(default_factory=dict, description="认证凭据（identifier + code）")

    model_config = {"populate_by_name": True}


class BindProviderResponse(BaseModel):
    """绑定新登录方式响应。"""

    provider: str = Field(..., description="登录方式")
    identifier: str = Field(..., description="脱敏后的标识")
    boundAt: str = Field(..., description="绑定时间（ISO 8601）")


class UserProfileResponse(BaseModel):
    """用户完整资料响应。"""

    uuid: str = Field(..., description="用户唯一标识")
    nickname: str = Field(..., description="昵称")
    avatarUrl: Optional[str] = Field(default=None, description="头像 URL")
    role: str = Field(default="user", description="角色")
    status: str = Field(default="active", description="状态")
    locale: str = Field(default="zh-CN", description="语言偏好")
    createdAt: Optional[str] = Field(default=None, description="创建时间（ISO 8601）")
    updatedAt: Optional[str] = Field(default=None, description="更新时间（ISO 8601）")


# ---------------------------------------------------------------------------
# 提醒渠道
# ---------------------------------------------------------------------------
class ReminderChannelItem(BaseModel):
    """单个提醒渠道。"""

    type: str = Field(..., description="渠道类型：web_push / wechat_subscribe")
    enabled: bool = Field(..., description="是否开启")


class UpdateReminderChannelsRequest(BaseModel):
    """更新提醒渠道设置。"""

    channels: list[ReminderChannelItem] = Field(..., description="提醒渠道列表")