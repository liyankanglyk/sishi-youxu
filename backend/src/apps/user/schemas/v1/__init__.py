"""v1 user schemas aggregator.

Export all request/response DTOs so route handlers can import them
from a single source.
"""

from src.apps.user.schemas.v1.auth import (
    # Request
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
    # Response
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
    # Auth requests
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
    # Auth responses
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
    # Common
    "PageMeta",
    # Feedback
    "FeedbackCreateRequest",
    # Sync
    "SyncOpItem",
    "SyncPushRequest",
    # Tag
    "TagCreateRequest",
    "TagOut",
    "TagUpdateRequest",
    # Task
    "BatchActionRequest",
    "ChecklistCreateRequest",
    "ChecklistUpdateRequest",
    "TaskCreateRequest",
    "TaskOut",
    "TaskUpdateRequest",
]
