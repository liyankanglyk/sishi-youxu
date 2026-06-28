"""面向用户端的 Pydantic DTO。"""
from src.apps.user.schemas.v1.auth import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RegisterRequest,
    TokenRefreshResponse,
    UserOut,
    WechatLoginRequest,
    WsTicketResponse,
)
from src.apps.user.schemas.v1.common import PageMeta
from src.apps.user.schemas.v1.task import TaskOut
from src.apps.user.schemas.v1.tag import TagOut

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RegisterRequest",
    "TokenRefreshResponse",
    "UserOut",
    "WechatLoginRequest",
    "WsTicketResponse",
    "PageMeta",
    "TaskOut",
    "TagOut",
]