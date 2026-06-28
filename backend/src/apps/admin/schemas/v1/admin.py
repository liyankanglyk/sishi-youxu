"""管理后台 DTO —— 字段名采用 camelCase 以匹配 API 规范。

所有请求模型均使用 camelCase 命名，以与 API 文档保持一致。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# =============================================================================
# 认证 DTO
# =============================================================================


class AdminLoginRequest(BaseModel):
    """管理员登录请求。"""

    username: str = Field(..., min_length=1, description="管理员用户名")
    password: str = Field(..., min_length=1, description="管理员密码")


class AdminRefreshRequest(BaseModel):
    """管理员 Token 刷新请求。"""

    refresh_token: str = Field(..., min_length=1, description="刷新令牌")


class AdminLogoutRequest(BaseModel):
    """管理员登出请求。"""

    refresh_token: str = Field(..., min_length=1, description="刷新令牌")


class AdminChangePasswordRequest(BaseModel):
    """管理员修改自己密码的请求。"""

    oldPassword: str = Field(..., min_length=1, description="当前密码")
    newPassword: str = Field(..., min_length=8, max_length=128, description="新密码（最少 8 位）")


class AdminResetUserPasswordRequest(BaseModel):
    """管理员重置用户密码的请求（无需旧密码）。"""

    newPassword: str = Field(..., min_length=8, max_length=128, description="新密码（最少 8 位）")


# =============================================================================
# 配置 DTO
# =============================================================================


class AdminConfigUpdateRequest(BaseModel):
    """更新系统配置请求（所有字段可选）。"""

    siteName: Optional[str] = Field(default=None, description="站点名称")
    siteLogo: Optional[str] = Field(default=None, description="站点 Logo URL")
    icpNumber: Optional[str] = Field(default=None, description="备案号")
    registrationEnabled: Optional[bool] = Field(default=None, description="是否开放注册")
    smsLoginEnabled: Optional[bool] = Field(default=None, description="是否开启短信登录")
    emailLoginEnabled: Optional[bool] = Field(default=None, description="是否开启邮箱登录")
    sensitiveWordFilterEnabled: Optional[bool] = Field(default=None, description="是否开启敏感词过滤")
    maintenanceMode: Optional[bool] = Field(default=None, description="是否开启维护模式")
    maintenanceMessage: Optional[str] = Field(default=None, description="维护模式提示信息")


# =============================================================================
# 反馈 DTO
# =============================================================================


class AdminFeedbackUpdateRequest(BaseModel):
    """更新反馈状态请求。"""

    status: str = Field(..., description="反馈状态：processing / resolved")


# =============================================================================
# 用户管理 DTO
# =============================================================================


class AdminUserUpdateRequest(BaseModel):
    """更新用户状态请求。"""

    status: str = Field(..., description="用户状态：active / disabled")


class AdminUserBatchRequest(BaseModel):
    """批量操作用户请求。"""

    action: str = Field(..., description="操作类型：disable / enable / delete")
    uuids: list[str] = Field(..., min_length=1, description="用户 UUID 列表")


# =============================================================================
# 响应 DTO（仅作参考保留）
# =============================================================================


class AdminUserOut(BaseModel):
    uuid: str
    nickname: str
    role: str
    status: str
    locale: str = "zh-CN"
    created_at: datetime
    updated_at: datetime


# =============================================================================
# 敏感词 DTO（Phase 4）
# =============================================================================


class SensitiveWordCreateRequest(BaseModel):
    """创建敏感词请求。"""
    word: str = Field(..., min_length=1, max_length=100, description="敏感词")
    level: int = Field(default=1, ge=1, le=3, description="过滤等级：1=替换 2=拦截 3=严格拦截")


class SensitiveWordUpdateRequest(BaseModel):
    """更新敏感词请求。"""
    word: Optional[str] = Field(default=None, min_length=1, max_length=100, description="敏感词")
    level: Optional[int] = Field(default=None, ge=1, le=3, description="过滤等级")


# =============================================================================
# IP 黑名单 DTO（Phase 4）
# =============================================================================


class IpBlacklistCreateRequest(BaseModel):
    """添加 IP 黑名单请求。"""
    ipAddress: str = Field(..., min_length=1, description="IP 地址（支持 CIDR 如 10.0.0.0/24）")
    reason: Optional[str] = Field(default=None, max_length=255, description="拉黑原因")
    expiresAt: Optional[str] = Field(default=None, description="过期时间 ISO 格式")


# =============================================================================
# 公告 DTO（Phase 4）
# =============================================================================


class AnnouncementCreateRequest(BaseModel):
    """创建公告请求。"""
    title: str = Field(..., min_length=1, max_length=200, description="公告标题")
    content: str = Field(..., min_length=1, description="公告内容")
    type: Literal["info", "warning", "critical"] = Field(default="info", description="公告类型")
    isPinned: bool = Field(default=False, description="是否置顶")
    isActive: bool = Field(default=True, description="是否启用")
    startTime: Optional[str] = Field(default=None, description="发布时间（ISO 格式）")
    endTime: Optional[str] = Field(default=None, description="下架时间（ISO 格式）")


class AnnouncementUpdateRequest(BaseModel):
    """更新公告请求。"""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200, description="公告标题")
    content: Optional[str] = Field(default=None, min_length=1, description="公告内容")
    type: Optional[Literal["info", "warning", "critical"]] = Field(default=None, description="公告类型")
    isPinned: Optional[bool] = Field(default=None, description="是否置顶")
    isActive: Optional[bool] = Field(default=None, description="是否启用")
    startTime: Optional[str] = Field(default=None, description="发布时间")
    endTime: Optional[str] = Field(default=None, description="下架时间")
