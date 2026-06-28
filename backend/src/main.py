"""FastAPI application entry point.

Skeleton wiring: middleware, routers, lifespan, healthcheck. No business logic.

Run with:
    uvicorn src.main:app --reload --port 8000

兼容端（Web / Capacitor / 微信小程序）：

- WebSocket 走 `/ws/notifications?token=<ticket>` 一次性 ticket 校验
  （小程序 `wx.connectSocket` 不支持自定义 Header，必须用 query 传 ticket）
- ticket 通过 `POST /api/v1/auth/ws-ticket` 用 access_token 换取
- 健康检查、`/sync/status` 是公开端点，便于小程序冷启动时校时/校通
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Response

# ---------------------------------------------------------------------------
# Swagger UI — 最常见的 OpenAPI 文档库
# JS/CSS 部署在本地 src/static/swagger-ui-*.{css,js}，无外部 CDN 依赖。
# 中文通过 JS 注入翻译（详见 SWAGGER_ZH_CN 字典 + MutationObserver 持续替换）。
# ---------------------------------------------------------------------------
_STATIC_DIR = Path(__file__).parent / "static"
_SWAGGER_VERSION = "5.17.14"

# Swagger UI zh-CN UI 字符串字典（DOM 文本替换兜底，兼容不支持 i18n 的版本）
SWAGGER_ZH_CN = {
    "2 Warning: Deprecated": "2 注意：已弃用",
    "Warning: Deprecated": "注意：已弃用",
    "Implementation Notes": "实现备注",
    "Response Class": "响应类",
    "Status": "状态",
    "Parameters": "参数",
    "Parameter": "参数",
    "Value": "值",
    "Description": "说明",
    "Parameter Type": "参数类型",
    "Data Type": "数据类型",
    "Response Messages": "响应消息",
    "HTTP Status Code": "HTTP 状态码",
    "Reason": "原因",
    "Response Model": "响应模型",
    "Request URL": "请求 URL",
    "Response Body": "响应体",
    "Response Code": "响应码",
    "Response Headers": "响应头",
    "Hide Response": "隐藏响应",
    "Headers": "请求头",
    "Try it out": "发送请求",
    "Execute": "执行",
    "Cancel": "取消",
    "Clear": "清空",
    "Loading": "加载中…",
    "required": "必填",
    "optional": "可选",
    "readOnly": "只读",
    "writeOnly": "只写",
    "deprecated": "已弃用",
    "allowEmptyValue": "允许空值",
    "Available values": "可用值",
    "Value (default)": "值（默认）",
    "Example Value": "示例值",
    "Model": "数据模型",
    "Models": "数据模型",
    "Model Schema": "模型 Schema",
    "Examples": "示例",
    "Example": "示例",
    "Type": "类型",
    "Format": "格式",
    "Default": "默认值",
    "Minimum": "最小值",
    "Maximum": "最大值",
    "Min length": "最小长度",
    "Max length": "最大长度",
    "Pattern": "正则",
    "Multiple Of": "倍数",
    "Enum (deprecated)": "枚举（已弃用）",
    "Tags": "标签",
    "Tag": "标签",
    "Servers": "服务地址",
    "Server": "服务",
    "Server Variables": "服务变量",
    "Security": "授权",
    "Security Definitions": "授权定义",
    "Authorize": "授权",
    "logout": "登出",
    "API": "API",
    "api": "API",
    "Get": "GET",
    "Post": "POST",
    "Put": "PUT",
    "Delete": "DELETE",
    "Patch": "PATCH",
    "Options": "OPTIONS",
    "Head": "HEAD",
    "click to set as parameter value": "点击设为参数值",
    "error rendering": "渲染错误",
    "not implemented in swagger": "Swagger 未实现",
    "Auth": "认证",
    "Username": "用户名",
    "Password": "密码",
    "Token": "令牌",
    "Bearer": "Bearer",
    "Basic": "Basic",
    "API key": "API Key",
    "Open": "打开",
    "Close": "关闭",
    "Confirm": "确认",
    "Save": "保存",
    "Add": "添加",
    "Edit": "编辑",
    "Remove": "移除",
    "Reset": "重置",
    "Skip to top": "回到顶部",
    "List Operations": "查看接口",
    "Expand Operations": "展开接口",
    "Raw": "原始",
    "Schema": "数据模型",
    "Example Value (default)": "示例值（默认）",
    "Select": "选择",
    "Add Parameter": "添加参数",
    "Name": "名称",
    "in": "位置",
    "Description": "说明",
    "Schema (default)": "Schema（默认）",
    "Path": "路径",
    "Query": "查询",
    "Header": "请求头",
    "Body": "请求体",
    "Form": "表单",
    "File": "文件",
    "Operations": "接口列表",
    "No operations defined for the API": "该 API 未定义任何接口",
    "Operation List": "接口列表",
    "Section Title": "分组",
    "Responses": "响应",
    "default": "默认",
    "Response Content Type": "响应内容类型",
    "Request Content Type": "请求内容类型",
    "Send Request": "发送请求",
    "Sending": "发送中",
    "No response": "暂无响应",
    "Network response": "网络响应",
    "Network Error": "网络错误",
    "Failed to fetch": "请求失败",
    "Error Encountered": "发生错误",
    "Warning": "警告",
    "Info": "信息",
    "Success": "成功",
    "show/hide": "显示/隐藏",
    "List": "列表",
    "View as JSON": "查看 JSON",
    "Sort": "排序",
    "Filter": "筛选",
    "Search": "搜索",
    "search": "搜索",
    "matched": "匹配",
    "results found": "条结果",
    "of": "共",
    "No results found": "未找到结果",
    "Download": "下载",
    "Downloadable": "可下载",
    "Content negotiation": "内容协商",
    "API Documentation": "API 接口文档",
    "Contact the developer": "联系开发者",
    "Terms of service": "服务条款",
    "Operation": "接口",
    "Deprecated": "已弃用",
    "Info": "基本信息",
    "Base URL": "基础 URL",
    "Schemes": "协议",
    "Consumes": "接收内容类型",
    "Produces": "返回内容类型",
    "deprecated": "已弃用",
    "Filters": "筛选",
    "Clear filters": "清除筛选",
    "Authorize Popup": "授权弹窗",
    "Available authorizations": "可选的鉴权方式",
    "Apply": "应用",
    "Example value (Raw)": "示例值（原始）",
    "Example value (Model)": "示例值（模型）",
    "Back to top": "回到顶部",
}

SWAGGER_UI_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>四时有序 API 文档</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📋</text></svg>">
  <link rel="stylesheet" type="text/css" href="/static/swagger-ui.css">
  <style>
    html, body { margin: 0; padding: 0; height: 100%; }
    body { font-family: "PingFang SC", "Microsoft YaHei", -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif; }
    /* 顶部信息栏 */
    .topbar { display: none; }  /* 隐藏 Swagger 默认 topbar */
    .information-container { padding: 16px 24px 8px; }
    /* 加载提示 */
    #swagger-loading {
      display: flex; align-items: center; justify-content: center;
      height: 100vh; color: #6b7280; font-size: 14px;
    }
    #swagger-loading::before {
      content: ""; width: 16px; height: 16px;
      border: 2px solid #d1d5db; border-top-color: #3b82f6;
      border-radius: 50%; margin-right: 8px;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div id="swagger-loading">正在加载 API 文档…</div>
  <div id="swagger-ui" style="display:none;"></div>

  <noscript>
    <div style="padding:24px;font-family:sans-serif;">
      <h2>需要启用 JavaScript</h2>
      <p>Swagger UI 是基于 JavaScript 的交互式 API 文档。请启用 JavaScript 后刷新页面。</p>
      <p>你也可以直接访问 <a href="/openapi.json">/openapi.json</a> 获取原始 OpenAPI 规范。</p>
    </div>
  </noscript>

  <script src="/static/swagger-ui-bundle.js"></script>
  <script src="/static/swagger-ui-standalone-preset.js"></script>
  <script>
  window.onload = function() {
    // Swagger UI 中文翻译（覆盖英文 UI 文本）
    var ZH = __SWAGGER_ZH_CN__;

    window.ui = SwaggerUIBundle({
      url: "/openapi.json",
      dom_id: "#swagger-ui",
      deepLinking: true,
      presets: [
        SwaggerUIBundle.presets.apis,
        SwaggerUIStandalonePreset
      ],
      plugins: [
        SwaggerUIBundle.plugins.DownloadUrl
      ],
      layout: "StandaloneLayout",
      defaultModelsExpandDepth: 1,
      defaultModelExpandDepth: 1,
      docExpansion: "list",
      filter: true,
      showRequestHeaders: false,
      showCommonExtensions: true,
      persistAuthorization: true,

      // ── 中文：覆盖 Swagger UI 默认英文文案 ──
      lang: {
        sortBy: ["alpha"],
        order: ["Query", "Header", "Path", "Body", "Form Data"],
      },
      onComplete: function() {
        // 替换内置文案
        try {
          if (window.ui && window.ui.lang && typeof window.ui.lang.translate === 'function') {
            // Swagger UI 提供 lang.translate，但必须先注入到 lang 对象
            // 这里直接 DOM 兜底
          }
          // 兜底：DOM 文本替换
          setTimeout(zhCNLocalize, 100);
          setTimeout(zhCNLocalize, 500);
          setTimeout(zhCNLocalize, 1500);
        } catch (e) {
          console.warn('zh-CN init failed:', e);
        }
      }
    });

    function zhCNLocalize() {
      var loading = document.getElementById('swagger-loading');
      if (loading) loading.style.display = 'none';
      var ui = document.getElementById('swagger-ui');
      if (ui) ui.style.display = 'block';

      // 替换所有可见的英文 UI 文本
      var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
      var node;
      var changed = 0;
      while ((node = walker.nextNode())) {
        var t = node.nodeValue;
        if (!t || t.length < 1) continue;
        // 跳过 URL / JSON / 字段名
        if (/^\\s*$/.test(t)) continue;
        var newT = t;
        Object.keys(ZH).forEach(function(k) {
          if (newT.indexOf(k) !== -1) {
            newT = newT.split(k).join(ZH[k]);
          }
        });
        if (newT !== t) {
          node.nodeValue = newT;
          changed++;
        }
      }
    }

    // 监听 DOM 变化持续翻译（Swagger UI 是动态渲染的）
    var observer = new MutationObserver(function() {
      zhCNLocalize();
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  };
  </script>
</body>
</html>"""

# 把字典注入到 HTML（替换 __SWAGGER_ZH_CN__ 占位符）
import json
SWAGGER_UI_HTML = SWAGGER_UI_HTML.replace(
    "__SWAGGER_ZH_CN__",
    json.dumps(SWAGGER_ZH_CN, ensure_ascii=False),
)

from src.core.config import settings
from src.core.database import close_db, init_db
from src.core.deps import WsUser
from src.core.logger import get_logger, setup_logging
from src.core.middleware import install_middlewares
from src.core.redis import close_redis, get_redis
from src.core.response import ok

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Best-effort startup/shutdown.

    The skeleton tolerates MySQL/Redis being offline — endpoints will fail
    individually when invoked, but the framework itself boots.
    """
    logger.info(
        "starting %s v%s (env=%s, timezone=%s)",
        settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV, settings.SERVER_TIMEZONE,
    )

    # --- Database: probe only ---
    try:
        await init_db()
        logger.info("database connection OK")
    except Exception as exc:
        logger.warning("database unavailable at startup: %s", exc)

    # --- Redis: probe only ---
    try:
        client = get_redis()
        await client.ping()
        logger.info("redis connection OK")
    except Exception as exc:
        logger.warning("redis unavailable at startup: %s", exc)

    # --- 微信小程序配置提示 ---
    if settings.WX_LOGIN_MOCK:
        logger.warning(
            "WX_LOGIN_MOCK=true: 微信 code2session 走 mock 模式（仅 dev/test）。"
            "生产环境务必配置 WX_APP_ID / WX_APP_SECRET 并关闭 mock。"
        )
    elif not settings.WX_APP_ID or not settings.WX_APP_SECRET:
        logger.warning(
            "WX_APP_ID / WX_APP_SECRET 未配置，微信小程序登录将不可用。"
        )

    yield

    logger.info("shutting down")
    try:
        await close_redis()
    except Exception as exc:
        logger.warning("redis close failed: %s", exc)
    try:
        await close_db()
    except Exception as exc:
        logger.warning("database close failed: %s", exc)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "四时有序 (sishi-youxu) — Phase 0~3 完成，67 条 API 全部实现。"
            "\n\n支持客户端：Web (Vue 3) / Capacitor (Android/iOS) / 微信小程序。"
            "\n\nWebSocket 鉴权：先用 access_token 调 `POST /api/v1/auth/ws-ticket`"
            "\n换取一次性 ticket，再用 `wss://host/ws/notifications?token=<ticket>` 连接。"
            "\n\n调试提示：点击右上角 `Authorize` 按钮，输入 `Bearer <access_token>` 即可全局鉴权。"
        ),
        # 禁用默认 docs_url/redoc_url，使用下方自定义的 Swagger UI
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    install_middlewares(app)

    # Healthcheck (no auth, no DB)
    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return ok({"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV})

    # Root
    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return ok(
            {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "docs": "/docs",
                "sync_status": f"{settings.API_V1_PREFIX}/sync/status",
            }
        )

    # API v1 mount
    from src.apps.admin import admin_router
    from src.apps.user import user_router

    app.include_router(user_router, prefix=settings.API_V1_PREFIX)
    app.include_router(admin_router, prefix=settings.API_V1_PREFIX)

    # ---------------------------------------------------------------------------
    # 注入 Bearer 安全方案到 OpenAPI schema
    # 让 Swagger UI 右上角 Authorize 按钮可用 —— 输入 access_token 后，
    # 所有标记 security=[bearerAuth] 的接口都会自动附加 Authorization 头。
    # ---------------------------------------------------------------------------
    def custom_openapi() -> dict:
        from fastapi.openapi.utils import get_openapi

        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # 注册用户端 Bearer
        schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schema["components"]["securitySchemes"]["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "在 Swagger UI 右上角点击 Authorize，输入 `Bearer <access_token>`。"
                "access_token 通过 `POST /api/v1/auth/tokens` 获取。"
            ),
        }
        # 注册管理端 Bearer（同一个 JWT，只是角色不同）
        schema["components"]["securitySchemes"]["adminBearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "管理员 token，通过 `POST /api/v1/admin/auth/tokens` 获取。",
        }

        # 自动给所有需要鉴权的接口附加 security 字段。
        # 鉴权接口列表（与源码中的路由依赖保持一致）：
        #   - 所有 /api/v1/admin/* 路径（除 login/refresh/logout/公开端点）
        #   - 所有 /api/v1/users/me/*（用户资料相关）
        #   - 所有 /api/v1/tasks*（任务相关）
        #   - 所有 /api/v1/tags*（标签相关）
        #   - 所有 /api/v1/notifications*（通知相关）
        #   - 所有 /api/v1/feedback*（GET 需要认证）
        #   - 所有 /api/v1/sync/push、/sync/pull（推送/拉取变更）
        #   - 所有 /api/v1/auth/tokens/logout、logout-all、ws-ticket
        # 公开接口：health, /, /docs, /openapi.json, 静态资源,
        #         /api/v1/sync/status,
        #         /api/v1/auth/tokens, /auth/tokens/refresh,
        #         /api/v1/users (注册), /auth/captcha*, /auth/sms/*, /auth/email/*, /auth/password/*, /auth/wechat/login,
        #         /api/v1/auth/login-methods, /api/v1/feedback (POST 提交支持匿名)
        #
        # 实现：基于路径白名单/黑名单做精确分类。

        # 黑名单：完全不需要认证的路径（公开）
        PUBLIC_PATHS_USER = {
            "/api/v1/auth/tokens",                          # 登录
            "/api/v1/auth/tokens/refresh",                  # 刷新 token
            "/api/v1/auth/captcha",                         # 获取图形验证码
            "/api/v1/auth/captcha/verify",                  # 校验图形验证码
            "/api/v1/auth/sms/send",                        # 发短信验证码
            "/api/v1/auth/sms/login",                       # 短信登录
            "/api/v1/auth/email/send",                      # 发邮箱验证码
            "/api/v1/auth/email/login",                     # 邮箱登录
            "/api/v1/auth/password/reset-request",          # 请求重置密码
            "/api/v1/auth/password/reset",                  # 执行重置密码
            "/api/v1/auth/wechat/login",                    # 微信登录
            "/api/v1/auth/login-methods",                   # 查询登录方式
            "/api/v1/users",                                # 注册新用户
            "/api/v1/feedback",                             # POST 提交反馈（支持匿名）
            "/api/v1/sync/status",                          # 服务端时间校准
        }
        PUBLIC_PATHS_ADMIN = {
            "/api/v1/admin/auth/tokens",                    # 管理员登录
            "/api/v1/admin/auth/tokens/refresh",            # 刷新管理员 token
        }
        # 全部 meta 端点
        META_PATHS = {
            "/", "/health", "/docs", "/openapi.json",
            "/docs/oauth2-redirect",
            "/static/swagger-ui.css",
            "/static/swagger-ui-bundle.js",
            "/static/swagger-ui-standalone-preset.js",
        }

        paths = schema.get("paths", {})
        for path, methods in paths.items():
            # 判断鉴权模式
            if path in META_PATHS or path.startswith("/static/"):
                # 公开
                sec = []
            elif path in PUBLIC_PATHS_USER:
                # 公开（注意 /api/v1/feedback POST 同时支持匿名，需要按方法区分）
                if path == "/api/v1/feedback" and "get" in methods:
                    # GET 我的反馈需要登录
                    sec = [{"bearerAuth": []}]
                else:
                    sec = []
            elif path in PUBLIC_PATHS_ADMIN:
                sec = []
            elif "/admin/" in path:
                # 管理端：除 login/refresh 外都需 admin 鉴权
                sec = [{"adminBearerAuth": []}]
            else:
                # 用户端其他接口：默认都需要 bearerAuth
                sec = [{"bearerAuth": []}]

            for method, op in methods.items():
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue
                # 兼容已有的显式声明
                if "security" in op and op["security"] is None:
                    op["security"] = sec
                else:
                    op["security"] = sec

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi

    # ---------------------------------------------------------------------------
    # 自定义 API 文档页（Swagger UI — 用户最终选择）
    # JS/CSS 完全本地化（src/static/swagger-ui-*.{css,js}），无外部 CDN 依赖。
    # 中文 UI 通过 JS 注入翻译。
    # ---------------------------------------------------------------------------
    @app.get("/docs", include_in_schema=False)
    async def docs_ui():
        return Response(
            content=SWAGGER_UI_HTML,
            media_type="text/html",
        )

    # Swagger UI 静态资源（CSS + 两个 JS）
    async def _serve_static(path: str, media_type: str):
        full = _STATIC_DIR / path
        if not full.exists():
            return Response(
                content=f"// missing {path}",
                media_type=media_type,
                status_code=404,
            )
        return Response(
            content=full.read_bytes(),
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/static/swagger-ui.css", include_in_schema=False)
    async def swagger_css():
        return await _serve_static("swagger-ui.css", "text/css; charset=utf-8")

    @app.get("/static/swagger-ui-bundle.js", include_in_schema=False)
    async def swagger_bundle():
        return await _serve_static(
            "swagger-ui-bundle.js", "application/javascript; charset=utf-8"
        )

    @app.get("/static/swagger-ui-standalone-preset.js", include_in_schema=False)
    async def swagger_standalone():
        return await _serve_static(
            "swagger-ui-standalone-preset.js", "application/javascript; charset=utf-8"
        )

    # ---------------------------------------------------------------------------
    # WebSocket（兼容小程序）
    # ---------------------------------------------------------------------------
    @app.websocket("/ws/notifications")
    async def ws_notifications(websocket: WebSocket, _user: WsUser = None) -> None:  # type: ignore[assignment]
        """用户端通知 ws。鉴权：query `?token=<ws-ticket>`，一次性消费。

        Phase 0 仅做握手/回声验证；Phase 3 接入实际通知推送。
        """
        # FastAPI 不会自动运行 Depends 校验 ws 的 Query；这里手动做一次。
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4401, reason="ws ticket missing")
            return
        from src.core.security import consume_ws_ticket
        user_uuid = await consume_ws_ticket(token)
        if not user_uuid:
            await websocket.close(code=4401, reason="ws ticket invalid or expired")
            return

        await websocket.accept()
        await websocket.send_json({
            "event": "hello",
            "channel": "notifications",
            "user_uuid": user_uuid,
        })
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            return

    @app.websocket("/admin/ws/notifications")
    async def ws_admin_notifications(websocket: WebSocket) -> None:
        """管理端通知 ws。鉴权：query `?token=<ws-ticket>`。"""
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4401, reason="ws ticket missing")
            return
        from src.core.security import consume_ws_ticket
        user_uuid = await consume_ws_ticket(token)
        if not user_uuid:
            await websocket.close(code=4401, reason="ws ticket invalid or expired")
            return

        await websocket.accept()
        await websocket.send_json({
            "event": "hello",
            "channel": "admin.notifications",
            "user_uuid": user_uuid,
        })
        try:
            while True:
                msg = await websocket.receive_text()
                if msg == "ping":
                    await websocket.send_text("pong")
        except WebSocketDisconnect:
            return

    return app


app = create_app()
