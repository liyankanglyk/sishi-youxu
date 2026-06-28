"""Pytest 配置与共享 fixtures。

- `client`             — 进程内 FastAPI TestClient（骨架风格，参照现有 test_health）。
- `random_email`       — 每个测试唯一的 email（避免 409 冲突）。
- `random_phone`       — 每个测试唯一的中国手机号（+86 + 9 位随机数字）。
- `register_user`      — 注册并返回 {tokens, identity, user} 供后续复用。
- `admin_login`        — 登录默认超级管理员（admin/123456），未 seed 时 skip。
- `skip_if_unavailable` — 守卫，让 MySQL/Redis 依赖测试优雅 skip
  （参照现有 test_health 在 500 时直接返回的模式）。
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import pytest

# 确保从 backend/ 运行 `pytest` 时 `src` 可被导入。
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# App & HTTP
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    """供外部 HTTP fixtures 使用的 API 基础 URL。"""
    return os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def app():
    """惰性导入 FastAPI app，供进程内 TestClient 使用。"""
    from src.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app):
    """每个测试一个 TestClient；lifespan 在首次请求时触发。"""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def skip_if_unavailable(client):
    """辅助函数：当 `/health` 响应外壳异常或 DB 写入失败（DB/Redis 不可用）时返回 True。

    在测试体中可这样使用：`if skip_if_unavailable(...): pytest.skip(...)`。
    """
    def _check() -> bool:
        try:
            resp = client.get("/health")
            if resp.status_code != 200:
                return True
            # 探测写接口 —— 用随机凭证注册。
            email = f"probe-{secrets.token_hex(4)}@example.com"
            r = client.post(
                "/api/v1/users",
                json={
                    "nickname": "probe",
                    "provider": "password",
                    "payload": {"identifier": email, "password": "Probe1234"},
                },
            )
            return r.status_code == 500
        except Exception:
            return True

    return _check


# ---------------------------------------------------------------------------
# 随机身份辅助（避免测试之间的 409 冲突）
# ---------------------------------------------------------------------------

@pytest.fixture()
def random_email() -> str:
    """每次测试调用一个唯一的 email。"""
    return f"test-{secrets.token_hex(6)}@example.com"


@pytest.fixture()
def random_phone() -> str:
    """每次测试调用一个唯一的 +86 手机号（最后 9 位随机）。"""
    suffix = "".join(str(secrets.randbelow(10)) for _ in range(9))
    return f"+86 1{suffix[:1]}{suffix[1:9]}"


@pytest.fixture()
def strong_password() -> str:
    """满足规范的密码（>= 8 字符，含大小写 + 数字）。"""
    return f"Test{secrets.token_hex(4)}1"  # always contains upper/lower/digit, >= 12 chars


# ---------------------------------------------------------------------------
# Authenticated-user fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def register_user(client, random_email, strong_password):
    """注册一个新用户；返回一个可调用对象以产出用户上下文。

    用法：
        ctx = register_user()                # 使用默认 email/password
        ctx = register_user(email=..., nickname=...)
        ctx["tokens"]["access_token"]         # Bearer 头取值
        ctx["user"]["uuid"]                   # 用户 UUID
        ctx["identity"]["email"]              # 登录标识

    Teardown：硬删除本次测试注册的所有 User（含 AuthIdentity / RefreshToken
    级联）+ 头像本地文件，保证 DB 不被测试数据污染。
    """
    created_uuids: list[str] = []

    def _make(
        *,
        email: str | None = None,
        nickname: str | None = None,
        password: str | None = None,
    ) -> dict:
        ident = email or random_email
        nick = nickname or f"tester-{secrets.token_hex(3)}"
        pwd = password or strong_password
        resp = client.post(
            "/api/v1/users",
            json={
                "nickname": nick,
                "provider": "password",
                "payload": {"identifier": ident, "password": pwd},
            },
        )
        assert resp.status_code == 200, f"register failed: {resp.status_code} {resp.text}"
        body = resp.json()["data"]
        ctx = {
            "tokens": {
                "access_token": body["access_token"],
                "refresh_token": body["refresh_token"],
                "token_type": body["token_type"],
                "expires_in": body["expires_in"],
            },
            "user": body["user"],
            "identity": {"email": ident, "password": pwd, "nickname": nick},
            "raw": body,
        }
        created_uuids.append(body["user"]["uuid"])
        # 加入 session 级清理队列
        _test_user_uuids.append(body["user"]["uuid"])
        return ctx

    yield _make

    # Teardown：硬删除本次测试产生的用户数据。
    if created_uuids:
        from tests._db_cleanup import purge_test_users

        purge_test_users(created_uuids)


@pytest.fixture()
def auth_headers(register_user):
    """便捷方法：为已注册用户生成 `Authorization: Bearer <access_token>` 头。"""
    def _headers() -> dict[str, str]:
        ctx = register_user()
        return {"Authorization": f"Bearer {ctx['tokens']['access_token']}"}

    return _headers


# ---------------------------------------------------------------------------
# Admin fixture (depends on init_admin.py having seeded admin/123456)
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_login(client):
    """返回一个可调用对象，用于登录默认超级管理员。

    若 admin/123456 未 seed，则跳过调用方测试（返回 None，使用时
    触发 pytest.skip）。
    """
    import pytest

    def _login() -> dict | None:
        resp = client.post(
            "/api/v1/admin/auth/tokens",
            json={"username": "admin", "password": "123456"},
        )
        if resp.status_code != 200:
            pytest.skip(f"admin/123456 未就绪：{resp.status_code} {resp.text[:120]}")
        return resp.json()["data"]

    return _login


__all__ = [
    "base_url",
    "app",
    "client",
    "skip_if_unavailable",
    "random_email",
    "random_phone",
    "strong_password",
    "register_user",
    "auth_headers",
    "admin_login",
]


# ---------------------------------------------------------------------------
# 会话级：收集测试产生的用户 UUID，session 结束时统一清理
# ---------------------------------------------------------------------------

_test_user_uuids: list[str] = []


@pytest.fixture(autouse=True, scope="session")
def _session_cleanup():
    """在 session 结束时清理所有通过 register_user fixture 创建的 UUID。"""
    yield
    if _test_user_uuids:
        from tests._db_cleanup import purge_test_users
        purge_test_users(list(set(_test_user_uuids)))
        _test_user_uuids.clear()


# ---------------------------------------------------------------------------
# 清理钩子
# ---------------------------------------------------------------------------

def pytest_runtest_teardown(item, nextitem):
    """在每个测试用例结束后，清理该测试产生的用户数据。"""
    try:
        from tests._db_cleanup import purge_test_users
        # 清理本测试产生的 UUID
        uuids = getattr(item, "_test_uuids", [])
        if uuids:
            purge_test_users(list(set(uuids)))
            item._test_uuids.clear()
        # 清理 _register_user helper 产生的 UUID
        if _test_user_uuids:
            purge_test_users(list(set(_test_user_uuids)))
            _test_user_uuids.clear()
    except Exception as exc:
        print(f"\n[conftest] teardown error: {exc}", flush=True)


def pytest_sessionfinish(session, exitstatus):
    """在 session 结束时清理所有 nickname 含 test-/u- 前缀的用户。"""
    try:
        from sqlalchemy import create_engine, text

        url = "mysql+pymysql://root:root@127.0.0.1:3306/sishi_youxu?charset=utf8mb4"
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT uuid FROM sishiyouxu_user "
                    "WHERE nickname LIKE 'test-%' OR nickname LIKE 'u-%'"
                )
            ).all()
            uuids = [r[0] for r in rows]
            if uuids:
                uuids_str = ",".join(f"'{u}'" for u in uuids)
                conn.execute(
                    text(f"DELETE FROM sishiyouxu_refresh_token WHERE user_uuid IN ({uuids_str})")
                )
                conn.execute(
                    text(f"DELETE FROM sishiyouxu_auth_identity WHERE user_uuid IN ({uuids_str})")
                )
                conn.execute(
                    text(f"DELETE FROM sishiyouxu_user WHERE uuid IN ({uuids_str})")
                )
                conn.commit()
        engine.dispose()
    except Exception:
        pass
