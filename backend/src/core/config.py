"""应用配置，从环境变量 / .env 文件加载。

骨架版本 —— 仅声明框架自身使用的配置面。
业务模块可以导入 `settings` 并按需扩展此清单。

设计要点（兼容 Web / Capacitor / 微信小程序）：

- JWT 同时支持 Authorization Header 和 URL Query（小程序 ws 场景只能走 query）
- WebSocket 认证走 ws-ticket 机制，避免依赖 Sec-WebSocket-Protocol
  （微信小程序 wx.connectSocket 不支持自定义 protocol 头）
- WeChat provider 配置预留（code2session 在 Phase 3 实现）
- 服务端时间统一 UTC，前端按客户端时区渲染
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置对象，通过 `get_settings()` 实例化一次。"""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- App ----------
    APP_NAME: str = "sishi-youxu"
    APP_ENV: Literal["dev", "test", "prod"] = "dev"
    APP_VERSION: str = "0.2.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = True

    # 服务端时区（用于 sync/status 校准、时间显示归一化）
    SERVER_TIMEZONE: str = "Asia/Shanghai"

    # ---------- Server ----------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1

    # ---------- Database (MySQL, async) ----------
    DATABASE_URL: str = Field(
        default="mysql+aiomysql://root:root@127.0.0.1:3306/sishi_youxu?charset=utf8mb4"
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_RECYCLE: int = 1800

    # ---------- Redis ----------
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    REDIS_KEY_PREFIX: str = "sishiyouxu"

    # ---------- JWT ----------
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ---------- WebSocket ticket ----------
    # 微信小程序无法在 ws 握手时设置 Authorization Header，
    # 必须走「先用 access_token 换取一次性 ticket，再用 ticket 连接 ws」的方案。
    WS_TICKET_EXPIRE_SECONDS: int = 60  # 一次性 ticket 的 TTL
    WS_HEARTBEAT_INTERVAL_SECONDS: int = 30
    WS_HEARTBEAT_TIMEOUT_SECONDS: int = 90

    # ---------- WeChat mini-program ----------
    # Phase 3 实现 code2session 登录时启用；
    # Phase 0 仅占位，无 appid 时走 mock 模式（仅 dev/test）
    WX_APP_ID: str = ""
    WX_APP_SECRET: str = ""
    WX_CODE2SESSION_URL: str = "https://api.weixin.qq.com/sns/jscode2session"
    WX_LOGIN_MOCK: bool = True  # dev/test 默认 mock，便于本地联调

    # ---------- CORS ----------
    # Web 端用 CORS，小程序不需要；保留 `*` + 显式 allow_credentials=false
    # 以兼容小程序通过 Nginx 反代时同源访问
    CORS_ORIGINS: list[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = False

    # ---------- Logging ----------
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "text"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """返回一个缓存的 Settings 实例。"""
    return Settings()


settings = get_settings()
