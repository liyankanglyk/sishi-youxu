"""v1 用户端 schema 聚合器。

统一导出所有请求/响应 DTO，便于路由处理器从单一来源导入。
"""

from src.apps.user.schemas.v1.auth import (
    # 请求
    BindProviderRequest,
    CaptchaVerifyRequest,
    ChangePasswordRequest,
    EmailCodeLoginRequest,
    EmailCodeSendRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetRequest,
    RefreshRequest,
    RegisterRequest,
    SmsCodeLoginRequest,
    SmsCodeSendRequest,
    UpdateProfileRequest,
    UpdateReminderChannelsRequest,
    WechatLoginRequest,
    # 响应
    AuthLinkageItem,
    AuthLinkageListResponse,
    AvatarUploadResponse,
    BindProviderResponse,
    CaptchaResponse,
    CaptchaVerifyResponse,
    ChangePasswordResponse,
    LinkTokenResponse,
    LoginMethodsResponse,
    LoginMethodItem,
    LoginResponse,
    LogoutResponse,
    PasswordResetResponse,
    TokenRefreshResponse,
    UserOut,
    UserProfileResponse,
    WsTicketResponse,
)
from src.apps.user.schemas.v1.common import PageMeta
from src.apps.user.schemas.v1.feedback import FeedbackCreateRequest
from src.apps.user.schemas.v1.sync import SyncOpItem, SyncPushRequest
from src.apps.user.schemas.v1.tag import TagCreateRequest, TagOut, TagUpdateRequest
from src.apps.user.schemas.v1.task import (
    BatchActionRequest,
    ChecklistCreateRequest,
    ChecklistUpdateRequest,
    TaskCreateRequest,
    TaskOut,
    TaskUpdateRequest,
)

__all__ = [
    # 认证请求
    "BindProviderRequest",
    "CaptchaVerifyRequest",
    "ChangePasswordRequest",
    "EmailCodeLoginRequest",
    "EmailCodeSendRequest",
    "LoginRequest",
    "LogoutRequest",
    "PasswordResetRequest",
    "RefreshRequest",
    "RegisterRequest",
    "SmsCodeLoginRequest",
    "SmsCodeSendRequest",
    "UpdateProfileRequest",
    "UpdateReminderChannelsRequest",
    "WechatLoginRequest",
    # 认证响应
    "AuthLinkageItem",
    "AuthLinkageListResponse",
    "AvatarUploadResponse",
    "BindProviderResponse",
    "CaptchaResponse",
    "CaptchaVerifyResponse",
    "ChangePasswordResponse",
    "LinkTokenResponse",
    "LoginMethodsResponse",
    "LoginMethodItem",
    "LoginResponse",
    "LogoutResponse",
    "PasswordResetResponse",
    "TokenRefreshResponse",
    "UserOut",
    "UserProfileResponse",
    "WsTicketResponse",
    # 通用
    "PageMeta",
    # 反馈
    "FeedbackCreateRequest",
    # 同步
    "SyncOpItem",
    "SyncPushRequest",
    # 标签
    "TagCreateRequest",
    "TagOut",
    "TagUpdateRequest",
    # 任务
    "BatchActionRequest",
    "ChecklistCreateRequest",
    "ChecklistUpdateRequest",
    "TaskCreateRequest",
    "TaskOut",
    "TaskUpdateRequest",
]
