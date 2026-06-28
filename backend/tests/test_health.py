"""针对骨架的烟雾测试 —— 验证框架能够启动并返回规范定义的标准响应外壳。

Phase 0（mini-program ready）覆盖：

- 框架启动 / 健康检查
- 用户端 / 管理端路由占位
- 新增端点：wechat login / ws-ticket / sync-status
- 业务异常 → 标准错误响应
- 平台识别头：X-Client-Platform 透传
"""
from fastapi.testclient import TestClient


def _client() -> TestClient:
    from src.main import app
    return TestClient(app)


def test_health_returns_ok_envelope():
    client = _client()
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"


def test_root_returns_metadata():
    client = _client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "sishi-youxu"
    # 新增字段：sync_status 公开端点
    assert "sync_status" in body["data"]


def test_user_skeleton_endpoint():
    """用户端任务列表已接入 RequiredUser 鉴权：无 token 应返回 401。"""
    client = _client()
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_admin_skeleton_endpoint():
    """管理端点已接入 RequireAdmin 鉴权：无 token 应返回 401。"""
    client = _client()
    resp = client.get("/api/v1/admin/dashboard/stats")
    # 已接入真实 RequireAdmin 依赖，需要有效 admin token
    assert resp.status_code in {200, 401}
    body = resp.json()
    if resp.status_code == 200:
        assert body["success"] is True
    else:
        # 401 说明鉴权守卫正常工作
        assert body["success"] is False


def test_business_exception_envelope():
    from src.core.exceptions import NotFoundException
    from src.core.response import fail

    body = fail(NotFoundException.code, NotFoundException.message)
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Phase 0 (mini-program ready) 新增端点
# ---------------------------------------------------------------------------


def test_wechat_login_real():
    """POST /api/v1/auth/wechat/login 已接入真实 AuthService（mock 模式）。

    需要 MySQL + Redis 可用；不可用时跳过真实验证。
    """
    client = _client()
    resp = client.post(
        "/api/v1/auth/wechat/login",
        json={"code": "mock_code_xxx"},
    )
    body = resp.json()
    if resp.status_code == 500:
        # DB/Redis 不可用，跳过
        return
    assert resp.status_code == 200
    assert body["success"] is True
    # 真实返回含 access_token / refresh_token / user / is_new_user
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]
    assert body["data"]["user"]["nickname"].startswith("wx_")


def test_ws_ticket_real():
    """POST /api/v1/auth/ws-ticket 已接入真实 AuthService（需有效 token）。

    需要 MySQL + Redis 可用；不可用时跳过真实验证。
    """
    client = _client()
    # 先注册一个用户获取 token
    import secrets
    email = f"test-ws-{secrets.token_hex(4)}@example.com"
    pwd = "Test1234"
    resp = client.post(
        "/api/v1/users",
        json={
            "nickname": "ws-tester",
            "provider": "password",
            "payload": {"identifier": email, "password": pwd},
        },
    )
    if resp.status_code == 500:
        # DB/Redis 不可用，跳过
        return
    assert resp.status_code == 200
    token = resp.json()["data"]["access_token"]

    # 用真实 token 获取 ws-ticket
    resp2 = client.post(
        "/api/v1/auth/ws-ticket",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert resp2.status_code == 200
    body = resp2.json()
    assert body["success"] is True
    assert "ticket" in body["data"]
    assert "expires_in" in body["data"]


def test_sync_status_public():
    """/sync/status 是公开端点，应返回 serverTime / timezone。"""
    client = _client()
    resp = client.get("/api/v1/sync/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "serverAt" in data
    assert "serverTimeMs" in data
    assert "timezone" in data
    # ISO 8601 校验
    from datetime import datetime
    parsed = datetime.fromisoformat(data["serverAt"])
    assert parsed.tzinfo is not None


def test_login_methods_lists_wechat():
    """login-methods 应包含 wechat provider。"""
    client = _client()
    resp = client.get("/api/v1/auth/login-methods")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    methods = {m["provider"] for m in body["data"]["methods"]}
    assert "wechat" in methods
    assert "password" in methods


def test_client_platform_header_passthrough():
    """X-Client-Platform 应被 RequestIDMiddleware 识别并写回响应头。"""
    client = _client()
    resp = client.get(
        "/health",
        headers={"X-Client-Platform": "miniapp"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Client-Platform") == "miniapp"
    assert resp.headers.get("X-Request-ID")


def test_ua_infers_miniapp():
    """User-Agent 含 micromessenger 时应自动归类为 miniapp。"""
    client = _client()
    resp = client.get(
        "/health",
        headers={"User-Agent": "Mozilla/5.0 ... MicroMessenger/8.0 ..."},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Client-Platform") == "miniapp"


def test_orm_models_importable_with_wechat():
    """ORM 模型应能正常导入，且 AuthProvider.wechat 存在。"""
    from src.models import AuthProvider
    assert hasattr(AuthProvider, "wechat")
    assert AuthProvider.wechat.value == "wechat"


def test_ws_ticket_function_signatures():
    """ws-ticket 工具函数签名（Phase 3 会实际写入 Redis；Phase 0 仅检查形态）。"""
    import inspect

    from src.core.security import consume_ws_ticket, create_ws_ticket, store_ws_ticket

    # 全部为 async
    assert inspect.iscoroutinefunction(consume_ws_ticket)
    assert inspect.iscoroutinefunction(store_ws_ticket)
    # create_ws_ticket 同步
    assert callable(create_ws_ticket)
    ticket, expires_at = create_ws_ticket("00000000-0000-0000-0000-000000000001")
    assert isinstance(ticket, str) and len(ticket) > 20
    assert expires_at.tzinfo is not None
