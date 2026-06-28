"""Pytest configuration & shared fixtures.

- `client`             — in-process FastAPI TestClient (skeleton-style, per existing test_health).
- `random_email`       — unique email per test (avoids 409 collisions).
- `random_phone`       — unique CN phone per test (+86 + 9 random digits).
- `register_user`      — registers + returns {tokens, identity, user} for downstream reuse.
- `admin_login`        — logs in default super admin (admin/123456), skips if not seeded.
- `skip_if_unavailable` — guard so MySQL/Redis-dependent tests skip gracefully
  (mirrors the existing test_health pattern of returning on 500).
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import pytest

# Ensure `src` is importable when running `pytest` from backend/.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# App & HTTP
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def base_url() -> str:
    """API base URL used by external HTTP fixtures."""
    return os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def app():
    """Lazily import the FastAPI app for in-process TestClient usage."""
    from src.main import app as fastapi_app

    return fastapi_app


@pytest.fixture()
def client(app):
    """Per-test TestClient; lifespan fires on first request."""
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def skip_if_unavailable(client):
    """Helper: returns True if `/health` envelope or DB write fails (DB/Redis down).

    Use as `if skip_if_unavailable(...): pytest.skip(...)` in test bodies.
    """
    def _check() -> bool:
        try:
            resp = client.get("/health")
            if resp.status_code != 200:
                return True
            # Probe a write endpoint — register with random creds.
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
# Random identity helpers (avoid 409 collisions between tests)
# ---------------------------------------------------------------------------

@pytest.fixture()
def random_email() -> str:
    """Unique email per test call."""
    return f"test-{secrets.token_hex(6)}@example.com"


@pytest.fixture()
def random_phone() -> str:
    """Unique +86 phone per test call (last 9 digits randomized)."""
    suffix = "".join(str(secrets.randbelow(10)) for _ in range(9))
    return f"+86 1{suffix[:1]}{suffix[1:9]}"


@pytest.fixture()
def strong_password() -> str:
    """Password that satisfies the spec (>= 8 chars, mixed case + digit)."""
    return f"Test{secrets.token_hex(4)}1"  # always contains upper/lower/digit, >= 12 chars


# ---------------------------------------------------------------------------
# Authenticated-user fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def register_user(client, random_email, strong_password):
    """Register a fresh user; return a callable that yields user context.

    Usage:
        ctx = register_user()                # default email/password
        ctx = register_user(email=..., nickname=...)
        ctx["tokens"]["access_token"]         # Bearer header value
        ctx["user"]["uuid"]                   # user UUID
        ctx["identity"]["email"]              # login identifier

    Teardown: 硬删除本次测试注册的所有 User（含 AuthIdentity / RefreshToken
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
    """Convenience: `Authorization: Bearer <access_token>` for the registered user."""
    def _headers() -> dict[str, str]:
        ctx = register_user()
        return {"Authorization": f"Bearer {ctx['tokens']['access_token']}"}

    return _headers


# ---------------------------------------------------------------------------
# Admin fixture (depends on init_admin.py having seeded admin/123456)
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_login(client):
    """Return a callable that logs in the default super admin.

    Skips the calling test if admin/123456 is not seeded (returns None and
    raises pytest.skip on use).
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
